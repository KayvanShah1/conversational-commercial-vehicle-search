from __future__ import annotations

from typing import Any

import duckdb
from vehicle_search_utils import OperationLogContext, get_logger, get_motherduck_connection

from vehicle_search_agent.models import (
    CatalogTopic,
    RankedVehicle,
    RankingBreakdown,
    SearchField,
    SearchFilters,
    VehicleRecord,
    VehicleSearchResult,
)
from vehicle_search_agent.settings import settings

logger = get_logger("VehicleSearch")

VEHICLE_COLUMNS = """
listing_id, make, model, year, price_inr, km_driven, fuel, payload_kg,
gvw_kg, vehicle_category, weight_class, body_type, axle_count, city,
papers_verified, condition, purpose_tags, spec_source_url
"""

RANKING_WEIGHTS = {
    "purpose": 0.30,
    "papers_verified": 0.15,
    "budget": 0.15,
    "mileage": 0.15,
    "condition": 0.15,
    "year": 0.10,
}
CONDITION_SCORE = {"excellent": 1.0, "good": 0.65, "fair": 0.30}
RELAXATION_PRIORITY = (
    SearchField.budget_max,
    SearchField.city,
    SearchField.body_type,
    SearchField.fuel,
    SearchField.papers_verified,
    SearchField.payload_min_kg,
    SearchField.gvw_min_kg,
    SearchField.make,
    SearchField.model,
    SearchField.vehicle_category,
    SearchField.weight_class,
    SearchField.budget_min,
)

CATALOG_TOPIC_COLUMNS = {
    CatalogTopic.cities: "city",
    CatalogTopic.vehicle_categories: "vehicle_category",
    CatalogTopic.body_types: "body_type",
    CatalogTopic.fuels: "fuel",
    CatalogTopic.makes: "make",
}


def _build_where(filters: SearchFilters) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    parameters: list[Any] = []

    comparisons = {
        "budget_min": ("price_inr >= ?", filters.budget_min),
        "budget_max": ("price_inr <= ?", filters.budget_max),
        "payload_min_kg": ("payload_kg IS NOT NULL AND payload_kg >= ?", filters.payload_min_kg),
        "gvw_min_kg": ("gvw_kg >= ?", filters.gvw_min_kg),
    }
    for clause, value in comparisons.values():
        if value is not None:
            clauses.append(clause)
            parameters.append(value)

    for field in ("city", "fuel", "body_type", "vehicle_category", "weight_class", "make", "model"):
        value = getattr(filters, field)
        if value is not None:
            clauses.append(f"LOWER({field}) = LOWER(?)")
            parameters.append(value)

    if filters.papers_verified is not None:
        clauses.append("papers_verified = ?")
        parameters.append(filters.papers_verified)

    return ("WHERE " + " AND ".join(clauses) if clauses else ""), parameters


def _records(cursor: duckdb.DuckDBPyConnection) -> list[VehicleRecord]:
    columns = [column[0] for column in cursor.description]
    return [VehicleRecord(**dict(zip(columns, row, strict=True))) for row in cursor.fetchall()]


def _matches(vehicle: VehicleRecord, filters: SearchFilters) -> bool:
    if filters.budget_min is not None and vehicle.price_inr < filters.budget_min:
        return False
    if filters.budget_max is not None and vehicle.price_inr > filters.budget_max:
        return False

    for field in ("city", "fuel", "body_type", "vehicle_category", "weight_class", "make", "model"):
        expected = getattr(filters, field)
        if expected is not None and getattr(vehicle, field).casefold() != expected.casefold():
            return False

    if filters.payload_min_kg is not None and (
        vehicle.payload_kg is None or vehicle.payload_kg < filters.payload_min_kg
    ):
        return False
    if filters.gvw_min_kg is not None and vehicle.gvw_kg < filters.gvw_min_kg:
        return False
    return filters.papers_verified is None or vehicle.papers_verified == filters.papers_verified


def _scaled(value: float, minimum: float, maximum: float, *, lower_is_better: bool) -> float:
    if maximum == minimum:
        return 1.0
    score = (value - minimum) / (maximum - minimum)
    return 1.0 - score if lower_is_better else score


def _rank(vehicles: list[VehicleRecord], filters: SearchFilters) -> list[RankedVehicle]:
    if not vehicles:
        return []

    prices = [vehicle.price_inr for vehicle in vehicles]
    kilometres = [vehicle.km_driven for vehicle in vehicles]
    years = [vehicle.year for vehicle in vehicles]
    ranges = {
        "price": (min(prices), max(prices)),
        "kilometres": (min(kilometres), max(kilometres)),
        "year": (min(years), max(years)),
    }

    weights = dict(RANKING_WEIGHTS)
    if filters.purpose is None:
        weights["purpose"] = 0
    if filters.budget_min is None and filters.budget_max is None:
        weights["budget"] = 0
    total_weight = sum(weights.values())

    ranked: list[RankedVehicle] = []
    for vehicle in vehicles:
        purpose_tags = {tag.casefold().replace("-", "_").replace(" ", "_") for tag in vehicle.purpose_tags}
        raw = {
            "purpose": float(filters.purpose in purpose_tags) if filters.purpose else 0.0,
            "papers_verified": float(vehicle.papers_verified),
            "budget": _scaled(vehicle.price_inr, *ranges["price"], lower_is_better=True),
            "mileage": _scaled(vehicle.km_driven, *ranges["kilometres"], lower_is_better=True),
            "condition": CONDITION_SCORE.get(vehicle.condition.casefold(), 0.0),
            "year": _scaled(vehicle.year, *ranges["year"], lower_is_better=False),
        }
        weighted = {name: raw[name] * weights[name] / total_weight for name in raw}
        ranked.append(RankedVehicle(vehicle=vehicle, score=RankingBreakdown(**weighted, total=sum(weighted.values()))))

    return sorted(ranked, key=lambda item: (-item.score.total, item.vehicle.listing_id))


def _find_relaxation(connection: duckdb.DuckDBPyConnection, filters: SearchFilters) -> str | None:
    all_vehicles = _records(connection.execute(f"SELECT {VEHICLE_COLUMNS} FROM vehicles"))
    for field in RELAXATION_PRIORITY:
        if getattr(filters, field.value) is None:
            continue
        relaxed = filters.model_copy(update={field.value: None})
        if any(_matches(vehicle, relaxed) for vehicle in all_vehicles):
            return field.value.replace("_", " ")
    return None


def search_catalog(
    filters: SearchFilters,
    changed_fields: list[SearchField],
    exclude_listing_ids: list[str] | None = None,
) -> VehicleSearchResult:
    operation = OperationLogContext("catalog_search")
    logger.info(
        "search_started",
        extra=operation.started_extra(tool="search_vehicles", filters=filters.model_dump(exclude_none=True)),
    )

    where_sql, parameters = _build_where(filters)
    sql = f"SELECT {VEHICLE_COLUMNS} FROM vehicles {where_sql} ORDER BY listing_id"

    with get_motherduck_connection(settings.motherduck, read_only=True) as connection:
        vehicles = _records(connection.execute(sql, parameters))
        relaxation = _find_relaxation(connection, filters) if not vehicles else None

    violations = [vehicle.listing_id for vehicle in vehicles if not _matches(vehicle, filters)]
    if violations:
        raise RuntimeError(f"Hard-filter invariant failed for listings: {violations}")

    excluded = set(exclude_listing_ids or [])
    ranked = [item for item in _rank(vehicles, filters) if item.vehicle.listing_id not in excluded]
    top_vehicles = ranked[:3]
    completed = operation.completed_extra(
        status="succeeded",
        tool="search_vehicles",
        filters=filters.model_dump(exclude_none=True),
        total_matches=len(vehicles),
        result_ids=[item.vehicle.listing_id for item in top_vehicles],
    )
    logger.info("search_completed", extra=completed)

    return VehicleSearchResult(
        executed_filters=filters,
        changed_fields=changed_fields,
        vehicles=top_vehicles,
        total_matches=len(vehicles),
        relaxation=relaxation,
        search_ms=completed["duration_ms"],
    )


def get_vehicles(listing_ids: list[str]) -> tuple[list[VehicleRecord], float]:
    operation = OperationLogContext("catalog_lookup")
    placeholders = ", ".join("?" for _ in listing_ids)
    sql = f"SELECT {VEHICLE_COLUMNS} FROM vehicles WHERE listing_id IN ({placeholders})"

    with get_motherduck_connection(settings.motherduck, read_only=True) as connection:
        vehicles = _records(connection.execute(sql, listing_ids))

    by_id = {vehicle.listing_id: vehicle for vehicle in vehicles}
    vehicles = [by_id[listing_id] for listing_id in listing_ids if listing_id in by_id]
    completed = operation.completed_extra(
        status="succeeded",
        tool="get_vehicle_details",
        listing_ids=listing_ids,
        found=len(vehicles),
    )
    logger.info("lookup_completed", extra=completed)
    return vehicles, completed["duration_ms"]


def get_catalog_options(topics: list[CatalogTopic]) -> tuple[dict[CatalogTopic, list[str]], float]:
    operation = OperationLogContext("catalog_options")
    selections = [
        f"SELECT '{topic.value}' AS topic, {CATALOG_TOPIC_COLUMNS[topic]} AS value FROM vehicles" for topic in topics
    ]
    sql = " UNION ".join(selections) + " ORDER BY topic, value"

    with get_motherduck_connection(settings.motherduck, read_only=True) as connection:
        rows = connection.execute(sql).fetchall()

    options = {topic: [] for topic in topics}
    for topic, value in rows:
        options[CatalogTopic(topic)].append(value)

    completed = operation.completed_extra(
        status="succeeded",
        tool="list_catalog_options",
        topics=[topic.value for topic in topics],
    )
    logger.info("catalog_options_completed", extra=completed)
    return options, completed["duration_ms"]
