from vehicle_search_utils import OperationLogContext, get_logger, get_motherduck_connection

from vehicle_search_agent.models import SearchField, SearchFilters, VehicleSearchResult
from vehicle_search_agent.search.query import VEHICLE_COLUMNS, build_where, records
from vehicle_search_agent.search.ranking import find_relaxation, matches, rank
from vehicle_search_agent.settings import settings

logger = get_logger("VehicleSearch")


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

    where_sql, parameters = build_where(filters)
    sql = f"SELECT {VEHICLE_COLUMNS} FROM vehicles {where_sql} ORDER BY listing_id"

    with get_motherduck_connection(settings.motherduck, read_only=True) as connection:
        vehicles = records(connection.execute(sql, parameters))
        relaxation = find_relaxation(connection, filters) if not vehicles else None

    violations = [vehicle.listing_id for vehicle in vehicles if not matches(vehicle, filters)]
    if violations:
        raise RuntimeError(f"Hard-filter invariant failed for listings: {violations}")

    excluded = set(exclude_listing_ids or [])
    ranked = [item for item in rank(vehicles, filters) if item.vehicle.listing_id not in excluded]
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
