from typing import Any

import duckdb
from vehicle_search_utils import OperationLogContext, get_logger, get_motherduck_connection

from vehicle_search_agent.models import CatalogTopic, SearchFilters, VehicleRecord
from vehicle_search_agent.settings import settings

logger = get_logger("VehicleSearch")

VEHICLE_COLUMNS = """
listing_id, make, model, year, price_inr, km_driven, fuel, payload_kg,
payload_is_estimated, gvw_kg, vehicle_category, weight_class, body_type, axle_count, city,
papers_verified, condition, purpose_tags, spec_source_url
"""

CATALOG_TOPIC_VALUES = {
    CatalogTopic.cities: "city",
    CatalogTopic.vehicle_categories: "vehicle_category",
    CatalogTopic.body_types: "body_type",
    CatalogTopic.fuels: "fuel",
    CatalogTopic.makes: "make",
    CatalogTopic.purposes: "UNNEST(purpose_tags)",
}


def build_where(filters: SearchFilters) -> tuple[str, list[Any]]:
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

    for field in ("city", "fuel", "body_type", "vehicle_category", "weight_class"):
        value = getattr(filters, field)
        if value is not None:
            clauses.append(f"LOWER({field}) = LOWER(?)")
            parameters.append(value)

    if filters.make is not None:
        clauses.append("POSITION(LOWER(?) IN LOWER(make)) > 0")
        parameters.append(filters.make)
    if filters.model is not None:
        clauses.append("POSITION(LOWER(?) IN LOWER(make || ' ' || model)) > 0")
        parameters.append(filters.model)

    if filters.papers_verified is not None:
        clauses.append("papers_verified = ?")
        parameters.append(filters.papers_verified)

    return ("WHERE " + " AND ".join(clauses) if clauses else ""), parameters


def records(cursor: duckdb.DuckDBPyConnection) -> list[VehicleRecord]:
    columns = [column[0] for column in cursor.description]
    return [VehicleRecord(**dict(zip(columns, row, strict=True))) for row in cursor.fetchall()]


def get_vehicles(listing_ids: list[str]) -> tuple[list[VehicleRecord], float]:
    operation = OperationLogContext("catalog_lookup")
    placeholders = ", ".join("?" for _ in listing_ids)
    sql = f"SELECT {VEHICLE_COLUMNS} FROM vehicles WHERE listing_id IN ({placeholders})"

    with get_motherduck_connection(settings.motherduck, read_only=True) as connection:
        vehicles = records(connection.execute(sql, listing_ids))

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
        f"SELECT DISTINCT '{topic.value}' AS topic, {CATALOG_TOPIC_VALUES[topic]} AS value FROM vehicles"
        for topic in topics
    ]
    sql = " UNION ALL ".join(selections) + " ORDER BY topic, value"

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
