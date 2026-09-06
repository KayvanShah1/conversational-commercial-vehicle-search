from collections.abc import Callable

from vehicle_search_agent.models import VehicleRecord
from vehicle_search_agent.response.details import format_payload, format_price

ComparisonResult = tuple[str, tuple[str, ...]]
ComparisonRenderer = Callable[[list[VehicleRecord]], ComparisonResult | None]


def _best_match(vehicles: list[VehicleRecord]) -> ComparisonResult:
    vehicle = vehicles[0]
    return f"Best match: {vehicle.make} {vehicle.model}", (vehicle.make, vehicle.model)


def _cheapest(vehicles: list[VehicleRecord]) -> ComparisonResult:
    vehicle = min(vehicles, key=lambda item: item.price_inr)
    value = format_price(vehicle.price_inr)
    return f"Cheapest: {vehicle.make} {vehicle.model} at {value}", (vehicle.make, vehicle.model, value)


def _lowest_km_driven(vehicles: list[VehicleRecord]) -> ComparisonResult:
    vehicle = min(vehicles, key=lambda item: item.km_driven)
    value = f"{vehicle.km_driven:,} km"
    return f"Lowest kilometres driven: {vehicle.make} {vehicle.model} at {value}", (
        vehicle.make,
        vehicle.model,
        value,
    )


def _highest_payload(vehicles: list[VehicleRecord]) -> ComparisonResult | None:
    known = [vehicle for vehicle in vehicles if vehicle.payload_kg is not None]
    if not known:
        return None

    vehicle = max(known, key=lambda item: item.payload_kg or 0)
    label, value = format_payload(vehicle)
    heading = f"Highest {label.casefold()}: {vehicle.make} {vehicle.model} at {value}"
    checks = [vehicle.make, vehicle.model]
    if vehicle.payload_is_estimated:
        checks.append("estimated")
    checks.append(value)
    return heading, tuple(checks)


COMPARISON_RENDERERS: dict[str, ComparisonRenderer] = {
    "best_match": _best_match,
    "cheapest": _cheapest,
    "lowest_km_driven": _lowest_km_driven,
    "highest_payload": _highest_payload,
}


def compare_vehicles(vehicles: list[VehicleRecord], comparison: str | None) -> ComparisonResult | None:
    renderer = COMPARISON_RENDERERS.get(comparison or "")
    return renderer(vehicles) if renderer else None
