from contextlib import contextmanager

import duckdb
import vehicle_search_agent.search as search_module
from vehicle_search_agent.models import CatalogTopic, SearchFilters


def _row(
    listing_id: str,
    *,
    year: int = 2015,
    price: int = 500_000,
    kilometres: int = 100_000,
    papers_verified: bool = True,
    condition: str = "fair",
    purpose: str = "logistics",
    weight_class: str = "light",
    model: str | None = None,
    city: str = "Pune",
    payload: int | None = 1000,
    payload_is_estimated: bool = False,
    gvw: int = 2000,
):
    return (
        listing_id,
        "Tata",
        model or f"Model {listing_id}",
        year,
        price,
        kilometres,
        "Diesel",
        payload,
        payload_is_estimated,
        gvw,
        "mini_truck",
        weight_class,
        "open",
        2,
        city,
        papers_verified,
        condition,
        [purpose],
        "https://example.com/spec",
    )


def _install_catalog(monkeypatch, rows):
    connection = duckdb.connect(":memory:")
    connection.execute(
        """
        CREATE TABLE vehicles (
            listing_id VARCHAR, make VARCHAR, model VARCHAR, year INTEGER,
            price_inr INTEGER, km_driven INTEGER, fuel VARCHAR, payload_kg INTEGER,
            payload_is_estimated BOOLEAN, gvw_kg INTEGER,
            vehicle_category VARCHAR, weight_class VARCHAR,
            body_type VARCHAR, axle_count INTEGER, city VARCHAR,
            papers_verified BOOLEAN, condition VARCHAR, purpose_tags VARCHAR[],
            spec_source_url VARCHAR
        )
        """
    )
    connection.executemany(
        "INSERT INTO vehicles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows
    )
    calls = {"count": 0}

    @contextmanager
    def local_connection(*args, **kwargs):
        calls["count"] += 1
        yield connection

    monkeypatch.setattr(search_module, "get_motherduck_connection", local_connection)
    return connection, calls


def test_search_ranks_every_matching_vehicle(monkeypatch):
    ordinary = [_row(f"VEH-{index:03}") for index in range(50)]
    best = _row(
        "VEH-999",
        year=2025,
        kilometres=0,
        papers_verified=False,
        condition="excellent",
    )
    connection, calls = _install_catalog(monkeypatch, [*ordinary, best])

    try:
        result = search_module.search_catalog(SearchFilters(), [])
    finally:
        connection.close()

    assert result.total_matches == 51
    assert result.vehicles[0].vehicle.listing_id == "VEH-999"
    assert calls["count"] == 1


def test_search_can_exclude_previously_shown_options(monkeypatch):
    rows = [_row(f"VEH-{index:03}") for index in range(6)]
    connection, _ = _install_catalog(monkeypatch, rows)

    try:
        first = search_module.search_catalog(SearchFilters(), [])
        first_ids = [item.vehicle.listing_id for item in first.vehicles]
        second = search_module.search_catalog(SearchFilters(), [], first_ids)
    finally:
        connection.close()

    second_ids = [item.vehicle.listing_id for item in second.vehicles]
    assert len(second_ids) == 3
    assert not set(first_ids).intersection(second_ids)


def test_zero_result_search_still_uses_one_connection(monkeypatch):
    connection, calls = _install_catalog(monkeypatch, [_row("VEH-001")])

    try:
        result = search_module.search_catalog(SearchFilters(city="Atlantis", budget_max=1_000_000), [])
    finally:
        connection.close()

    assert result.total_matches == 0
    assert result.relaxation == "city"
    assert calls["count"] == 1


def test_purpose_matching_uses_normalized_values():
    vehicle = search_module.VehicleRecord.model_validate(
        dict(
            zip(
                [column.strip() for column in search_module.VEHICLE_COLUMNS.replace("\n", "").split(",")],
                _row("VEH-001", purpose="City Delivery"),
                strict=True,
            )
        )
    )

    ranked = search_module._rank([vehicle], SearchFilters(purpose="city_delivery"))

    assert ranked[0].score.purpose > 0


def test_weight_class_is_a_hard_filter(monkeypatch):
    connection, _ = _install_catalog(
        monkeypatch,
        [_row("VEH-001", weight_class="light"), _row("VEH-002", weight_class="heavy")],
    )

    try:
        result = search_module.search_catalog(SearchFilters(weight_class="heavy"), [])
    finally:
        connection.close()

    assert result.total_matches == 1
    assert result.vehicles[0].vehicle.listing_id == "VEH-002"


def test_payload_and_gvw_constraints_are_both_required(monkeypatch):
    connection, _ = _install_catalog(
        monkeypatch,
        [
            _row("LOW-PAYLOAD", payload=1500, gvw=10_000),
            _row("LOW-GVW", payload=2500, gvw=9000),
            _row("MATCH", payload=2500, gvw=10_000),
        ],
    )

    try:
        result = search_module.search_catalog(SearchFilters(payload_min_kg=2000, gvw_min_kg=10_000), [])
    finally:
        connection.close()

    assert [item.vehicle.listing_id for item in result.vehicles] == ["MATCH"]


def test_search_accepts_a_partial_model_name_with_its_make(monkeypatch):
    connection, _ = _install_catalog(
        monkeypatch,
        [_row("VEH-ACE", model="Ace Gold"), _row("VEH-INTRA", model="Intra V30")],
    )

    try:
        result = search_module.search_catalog(SearchFilters(model="Tata Ace"), [])
    finally:
        connection.close()

    assert result.total_matches == 1
    assert result.vehicles[0].vehicle.model == "Ace Gold"


def test_catalog_options_use_one_connection_and_return_unique_facets(monkeypatch):
    rows = [
        _row("VEH-001"),
        _row("VEH-002", purpose="city_delivery", city="Mumbai"),
        _row("VEH-003"),
    ]
    connection, calls = _install_catalog(monkeypatch, rows)

    try:
        options, _ = search_module.get_catalog_options([CatalogTopic.cities, CatalogTopic.fuels, CatalogTopic.purposes])
    finally:
        connection.close()

    assert options == {
        CatalogTopic.cities: ["Mumbai", "Pune"],
        CatalogTopic.fuels: ["Diesel"],
        CatalogTopic.purposes: ["city_delivery", "logistics"],
    }
    assert calls["count"] == 1


def test_multi_vehicle_lookup_uses_one_connection_and_preserves_result_order(monkeypatch):
    connection, calls = _install_catalog(monkeypatch, [_row("VEH-001"), _row("VEH-002")])

    try:
        vehicles, _ = search_module.get_vehicles(["VEH-002", "VEH-001"])
    finally:
        connection.close()

    assert [vehicle.listing_id for vehicle in vehicles] == ["VEH-002", "VEH-001"]
    assert calls["count"] == 1
