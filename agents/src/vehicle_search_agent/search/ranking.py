import duckdb

from vehicle_search_agent.models import (
    RankedVehicle,
    RankingBreakdown,
    SearchField,
    SearchFilters,
    VehicleRecord,
)
from vehicle_search_agent.search.query import VEHICLE_COLUMNS, records

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
RELAXATION_LABELS = {
    SearchField.budget_min: "budget",
    SearchField.budget_max: "budget",
    SearchField.payload_min_kg: "payload",
    SearchField.gvw_min_kg: "GVW",
}


def matches(vehicle: VehicleRecord, filters: SearchFilters) -> bool:
    if filters.budget_min is not None and vehicle.price_inr < filters.budget_min:
        return False
    if filters.budget_max is not None and vehicle.price_inr > filters.budget_max:
        return False

    for field in ("city", "fuel", "body_type", "vehicle_category", "weight_class"):
        expected = getattr(filters, field)
        if expected is not None and getattr(vehicle, field).casefold() != expected.casefold():
            return False

    if filters.make is not None and filters.make.casefold() not in vehicle.make.casefold():
        return False
    catalog_name = f"{vehicle.make} {vehicle.model}".casefold()
    if filters.model is not None and filters.model.casefold() not in catalog_name:
        return False

    if filters.payload_min_kg is not None and (
        vehicle.payload_kg is None or vehicle.payload_kg < filters.payload_min_kg
    ):
        return False
    if filters.gvw_min_kg is not None and vehicle.gvw_kg < filters.gvw_min_kg:
        return False
    return filters.papers_verified is None or vehicle.papers_verified == filters.papers_verified


def scaled(value: float, minimum: float, maximum: float, *, lower_is_better: bool) -> float:
    if maximum == minimum:
        return 1.0
    score = (value - minimum) / (maximum - minimum)
    return 1.0 - score if lower_is_better else score


def rank(vehicles: list[VehicleRecord], filters: SearchFilters) -> list[RankedVehicle]:
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
            "budget": scaled(vehicle.price_inr, *ranges["price"], lower_is_better=True),
            "mileage": scaled(vehicle.km_driven, *ranges["kilometres"], lower_is_better=True),
            "condition": CONDITION_SCORE.get(vehicle.condition.casefold(), 0.0),
            "year": scaled(vehicle.year, *ranges["year"], lower_is_better=False),
        }
        weighted = {name: raw[name] * weights[name] / total_weight for name in raw}
        ranked.append(RankedVehicle(vehicle=vehicle, score=RankingBreakdown(**weighted, total=sum(weighted.values()))))

    return sorted(ranked, key=lambda item: (-item.score.total, item.vehicle.listing_id))


def find_relaxation(connection: duckdb.DuckDBPyConnection, filters: SearchFilters) -> str | None:
    all_vehicles = records(connection.execute(f"SELECT {VEHICLE_COLUMNS} FROM vehicles"))
    active_fields = [field for field in RELAXATION_PRIORITY if getattr(filters, field.value) is not None]
    for field in active_fields:
        relaxed = filters.model_copy(update={field.value: None})
        if any(matches(vehicle, relaxed) for vehicle in all_vehicles):
            return RELAXATION_LABELS.get(field, field.value.replace("_", " "))
    if active_fields:
        field = active_fields[0]
        return RELAXATION_LABELS.get(field, field.value.replace("_", " "))
    return None
