from collections.abc import Callable

from vehicle_search_agent.models import DetailField, VehicleRecord
from vehicle_search_agent.response.models import DetailValue


def format_price(price_inr: int) -> str:
    if price_inr < 100_000:
        return f"INR {price_inr:,}"
    lakh = price_inr / 100_000
    formatted = str(int(lakh)) if lakh.is_integer() else f"{lakh:.1f}"
    return f"INR {formatted}L"


def _join_naturally(values: list[str]) -> str:
    if len(values) < 2:
        return "".join(values)
    if len(values) == 2:
        return " and ".join(values)
    return ", ".join(values[:-1]) + f", and {values[-1]}"


def format_payload(vehicle: VehicleRecord) -> tuple[str, str]:
    label = "Estimated payload" if vehicle.payload_is_estimated else "Payload"
    if vehicle.payload_kg is None:
        return label, "not listed"
    prefix = "approximately " if vehicle.payload_is_estimated else ""
    return label, f"{prefix}{vehicle.payload_kg:,} kg"


DetailRenderer = Callable[[VehicleRecord], DetailValue]


def _render_year(vehicle: VehicleRecord) -> DetailValue:
    value = str(vehicle.year)
    return DetailValue(f"year {value}", f"is a {value} model", "Year", value, (value,))


def _render_price(vehicle: VehicleRecord) -> DetailValue:
    value = format_price(vehicle.price_inr)
    return DetailValue(f"price {value}", f"costs {value}", "Price", value, (value,))


def _render_km_driven(vehicle: VehicleRecord) -> DetailValue:
    value = f"{vehicle.km_driven:,} km"
    return DetailValue(value, f"has covered {value}", "Kilometres driven", value, (str(vehicle.km_driven),))


def _render_fuel(vehicle: VehicleRecord) -> DetailValue:
    value = vehicle.fuel
    return DetailValue(f"fuel {value}", f"runs on {value}", "Fuel", value, (value,))


def _render_payload(vehicle: VehicleRecord) -> DetailValue:
    label, value = format_payload(vehicle)
    article = "an" if vehicle.payload_is_estimated else "a"
    checks = ("estimated",) if vehicle.payload_is_estimated else ()
    checks += (str(vehicle.payload_kg) if vehicle.payload_kg is not None else "not listed",)
    return DetailValue(
        f"{label.casefold()} {value}",
        f"has {article} {label.casefold()} of {value}",
        label,
        value,
        checks,
    )


def _render_gvw(vehicle: VehicleRecord) -> DetailValue:
    value = f"{vehicle.gvw_kg:,} kg"
    return DetailValue(f"GVW {value}", f"has a GVW of {value}", "GVW", value, (str(vehicle.gvw_kg),))


def _render_body_type(vehicle: VehicleRecord) -> DetailValue:
    value = vehicle.body_type
    article = "an" if value[:1].casefold() in "aeiou" else "a"
    return DetailValue(f"body type {value}", f"has {article} {value} body", "Body", value.title(), (value,))


def _render_city(vehicle: VehicleRecord) -> DetailValue:
    value = vehicle.city
    return DetailValue(f"city {value}", f"is listed in {value}", "City", value, (value,))


def _render_papers_verified(vehicle: VehicleRecord) -> DetailValue:
    value = "Verified" if vehicle.papers_verified else "Not verified"
    check = "verified" if vehicle.papers_verified else "not verified"
    clause = "has verified papers" if vehicle.papers_verified else "does not have verified papers"
    return DetailValue(f"papers {value.casefold()}", clause, "Papers", value, (check,))


def _render_condition(vehicle: VehicleRecord) -> DetailValue:
    value = vehicle.condition
    return DetailValue(f"condition {value}", f"is in {value} condition", "Condition", value.title(), (value,))


def _render_purpose_tags(vehicle: VehicleRecord) -> DetailValue:
    values = tuple(tag.replace("_", " ") for tag in vehicle.purpose_tags)
    display = ", ".join(values)
    return DetailValue(
        f"listed uses {display}",
        f"is listed for {_join_naturally(list(values))}",
        "Listed uses",
        display,
        values,
    )


def _render_vehicle_category(vehicle: VehicleRecord) -> DetailValue:
    value = vehicle.vehicle_category.replace("_", " ")
    return DetailValue(f"category {value}", f"is a {value}", "Category", value.title(), (value,))


def _render_weight_class(vehicle: VehicleRecord) -> DetailValue:
    value = vehicle.weight_class
    return DetailValue(
        f"size class {value}", f"is in the {value} weight class", "Weight class", value.title(), (value,)
    )


def _render_axle_count(vehicle: VehicleRecord) -> DetailValue:
    value = str(vehicle.axle_count)
    return DetailValue(f"axles {value}", f"has {value} axles", "Axles", value, (value,))


def _render_spec_source_url(vehicle: VehicleRecord) -> DetailValue:
    value = vehicle.spec_source_url
    return DetailValue(
        f"specification source {value}",
        None,
        "Specification source",
        f"[View manufacturer specifications]({value})",
        (value,),
    )


DETAIL_RENDERERS: dict[DetailField, DetailRenderer] = {
    DetailField.year: _render_year,
    DetailField.price: _render_price,
    DetailField.km_driven: _render_km_driven,
    DetailField.fuel: _render_fuel,
    DetailField.payload: _render_payload,
    DetailField.gvw: _render_gvw,
    DetailField.body_type: _render_body_type,
    DetailField.city: _render_city,
    DetailField.papers_verified: _render_papers_verified,
    DetailField.condition: _render_condition,
    DetailField.purpose_tags: _render_purpose_tags,
    DetailField.vehicle_category: _render_vehicle_category,
    DetailField.weight_class: _render_weight_class,
    DetailField.axle_count: _render_axle_count,
    DetailField.spec_source_url: _render_spec_source_url,
}


def render_detail(vehicle: VehicleRecord, field: DetailField) -> DetailValue:
    try:
        renderer = DETAIL_RENDERERS[field]
    except KeyError:
        raise ValueError(f"Unsupported detail field: {field}") from None
    return renderer(vehicle)
