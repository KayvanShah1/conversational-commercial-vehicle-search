import re
from collections.abc import Callable
from dataclasses import dataclass

from vehicle_search_agent.models import CatalogTopic, DetailField, RankedVehicle, VehicleRecord, VehicleSearchResult


@dataclass(frozen=True)
class GroundedResponse:
    fallback: str
    facts: tuple[str, ...]
    checks: tuple[tuple[str, ...], ...]
    display_markdown: str | None = None


@dataclass(frozen=True)
class DetailValue:
    fact: str
    spoken_clause: str | None
    display_label: str
    display_value: str
    checks: tuple[str, ...]


def _price(price_inr: int) -> str:
    if price_inr < 100_000:
        return f"INR {price_inr:,}"
    lakh = price_inr / 100_000
    formatted = str(int(lakh)) if lakh.is_integer() else f"{lakh:.1f}"
    return f"INR {formatted}L"


def _reason(ranked: RankedVehicle, purpose: str | None) -> str:
    vehicle = ranked.vehicle
    if purpose and ranked.score.purpose > 0:
        return purpose.replace("_", " ")
    if vehicle.papers_verified:
        return "verified papers"
    return f"{vehicle.condition} condition"


def _join_naturally(values: list[str]) -> str:
    if len(values) < 2:
        return "".join(values)
    if len(values) == 2:
        return " and ".join(values)
    return ", ".join(values[:-1]) + f", and {values[-1]}"


def _payload(vehicle: VehicleRecord) -> tuple[str, str]:
    label = "Estimated payload" if vehicle.payload_is_estimated else "Payload"
    if vehicle.payload_kg is None:
        return label, "not listed"
    prefix = "approximately " if vehicle.payload_is_estimated else ""
    return label, f"{prefix}{vehicle.payload_kg:,} kg"


def _render_detail(vehicle: VehicleRecord, field: DetailField) -> DetailValue:
    match field:
        case DetailField.year:
            value = str(vehicle.year)
            return DetailValue(f"year {value}", f"is a {value} model", "Year", value, (value,))
        case DetailField.price:
            value = _price(vehicle.price_inr)
            return DetailValue(f"price {value}", f"costs {value}", "Price", value, (value,))
        case DetailField.km_driven:
            value = f"{vehicle.km_driven:,} km"
            return DetailValue(value, f"has covered {value}", "Kilometres driven", value, (str(vehicle.km_driven),))
        case DetailField.fuel:
            value = vehicle.fuel
            return DetailValue(f"fuel {value}", f"runs on {value}", "Fuel", value, (value,))
        case DetailField.payload:
            label, value = _payload(vehicle)
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
        case DetailField.gvw:
            value = f"{vehicle.gvw_kg:,} kg"
            return DetailValue(f"GVW {value}", f"has a GVW of {value}", "GVW", value, (str(vehicle.gvw_kg),))
        case DetailField.body_type:
            value = vehicle.body_type
            article = "an" if value[:1].casefold() in "aeiou" else "a"
            return DetailValue(f"body type {value}", f"has {article} {value} body", "Body", value.title(), (value,))
        case DetailField.city:
            value = vehicle.city
            return DetailValue(f"city {value}", f"is listed in {value}", "City", value, (value,))
        case DetailField.papers_verified:
            value = "Verified" if vehicle.papers_verified else "Not verified"
            check = "verified" if vehicle.papers_verified else "not verified"
            clause = "has verified papers" if vehicle.papers_verified else "does not have verified papers"
            return DetailValue(f"papers {value.casefold()}", clause, "Papers", value, (check,))
        case DetailField.condition:
            value = vehicle.condition
            return DetailValue(
                f"condition {value}", f"is in {value} condition", "Condition", value.title(), (value,)
            )
        case DetailField.purpose_tags:
            values = tuple(tag.replace("_", " ") for tag in vehicle.purpose_tags)
            display = ", ".join(values)
            return DetailValue(
                f"listed uses {display}",
                f"is listed for {_join_naturally(list(values))}",
                "Listed uses",
                display,
                values,
            )
        case DetailField.vehicle_category:
            value = vehicle.vehicle_category.replace("_", " ")
            return DetailValue(f"category {value}", f"is a {value}", "Category", value.title(), (value,))
        case DetailField.weight_class:
            value = vehicle.weight_class
            return DetailValue(
                f"size class {value}", f"is in the {value} weight class", "Weight class", value.title(), (value,)
            )
        case DetailField.axle_count:
            value = str(vehicle.axle_count)
            return DetailValue(f"axles {value}", f"has {value} axles", "Axles", value, (value,))
        case DetailField.spec_source_url:
            value = vehicle.spec_source_url
            return DetailValue(
                f"specification source {value}",
                None,
                "Specification source",
                f"[View manufacturer specifications]({value})",
                (value,),
            )
    raise ValueError(f"Unsupported detail field: {field}")


SPOKEN_FIELD_GROUPS = (
    (DetailField.city,),
    (DetailField.price, DetailField.km_driven, DetailField.fuel),
    (DetailField.payload, DetailField.gvw, DetailField.axle_count),
    (DetailField.papers_verified, DetailField.condition, DetailField.weight_class),
    (DetailField.purpose_tags,),
)


def _identity_sentence(vehicle: VehicleRecord, details: dict[DetailField, DetailValue]) -> str:
    name = f"{vehicle.make} {vehicle.model}"
    year = details.get(DetailField.year)
    category = details.get(DetailField.vehicle_category)
    body = details.get(DetailField.body_type)

    if year and category:
        introduction = f"{name} is a {year.display_value} model in the {category.display_value.casefold()} category"
    elif year:
        introduction = f"{name} {year.spoken_clause}"
    elif category:
        introduction = f"{name} {category.spoken_clause}"
    else:
        introduction = ""
    if body:
        introduction += f" and {body.spoken_clause}" if introduction else f"{name} {body.spoken_clause}"
    return introduction + "." if introduction else ""


def _detail_summary(vehicle: VehicleRecord, details: dict[DetailField, DetailValue]) -> str:
    name = f"{vehicle.make} {vehicle.model}"
    sentences = [sentence] if (sentence := _identity_sentence(vehicle, details)) else []
    for group in SPOKEN_FIELD_GROUPS:
        clauses = [detail.spoken_clause for field in group if (detail := details.get(field)) and detail.spoken_clause]
        if clauses:
            subject = "It" if sentences else name
            sentences.append(f"{subject} {_join_naturally(clauses)}.")

    if source := details.get(DetailField.spec_source_url):
        sentences.append(f"The specification source for {name} is {source.checks[0]}.")
    return " ".join(sentences)


def _multiple_detail_summary(
    vehicles: list[VehicleRecord],
    details_by_vehicle: list[dict[DetailField, DetailValue]],
) -> str:
    sentences = [f"I found {len(vehicles)} matching listings."]
    for vehicle, details in zip(vehicles, details_by_vehicle, strict=True):
        name = f"{vehicle.make} {vehicle.model}"
        qualifiers = [
            detail.display_value
            for field in (DetailField.year, DetailField.city)
            if (detail := details.get(field))
        ]
        subject = f"The {' '.join(qualifiers)} {name} listing" if qualifiers else name
        highlights = [
            detail.spoken_clause
            for field in (DetailField.price, DetailField.km_driven, DetailField.payload, DetailField.gvw)
            if (detail := details.get(field)) and detail.spoken_clause
        ]
        sentences.append(f"{subject} {_join_naturally(highlights)}." if highlights else f"{subject} is included.")

    first_details = details_by_vehicle[0]
    if DetailField.fuel in first_details and len({vehicle.fuel for vehicle in vehicles}) == 1:
        sentences.append(f"All run on {first_details[DetailField.fuel].display_value}.")
    if DetailField.papers_verified in first_details and all(vehicle.papers_verified for vehicle in vehicles):
        sentences.append("All have verified papers.")
    sentences.append("The full specifications and source links are shown on screen.")
    return " ".join(sentences)


def search_response(result: VehicleSearchResult) -> GroundedResponse:
    if not result.vehicles:
        facts = ["I couldn't find an exact match."]
        if result.relaxation:
            facts.append(f"We could try relaxing the {result.relaxation} constraint.")
        response = " ".join(facts)
        checks = tuple((fact,) for fact in facts)
    else:
        reasons = [_reason(ranked, result.executed_filters.purpose) for ranked in result.vehicles]
        facts = [
            f"{ranked.vehicle.make} {ranked.vehicle.model} at {_price(ranked.vehicle.price_inr)}, with {reason}"
            for ranked, reason in zip(result.vehicles, reasons, strict=True)
        ]
        checks = tuple(
            (
                f"{ranked.vehicle.make} {ranked.vehicle.model}",
                _price(ranked.vehicle.price_inr),
                "verified" if ranked.vehicle.papers_verified else reason,
            )
            for ranked, reason in zip(result.vehicles, reasons, strict=True)
        )
        response = f"Top match: {facts[0]}."
        if len(facts) > 1:
            response += " Other options: " + "; ".join(facts[1:]) + "."

    return GroundedResponse(response, tuple(facts), checks)


ComparisonResult = tuple[str, tuple[str, ...]]


def _best_match(vehicles: list[VehicleRecord]) -> ComparisonResult:
    vehicle = vehicles[0]
    return f"Best match: {vehicle.make} {vehicle.model}", (vehicle.make, vehicle.model)


def _cheapest(vehicles: list[VehicleRecord]) -> ComparisonResult:
    vehicle = min(vehicles, key=lambda item: item.price_inr)
    value = _price(vehicle.price_inr)
    return f"Cheapest: {vehicle.make} {vehicle.model} at {value}", (vehicle.make, vehicle.model, value)


def _lowest_mileage(vehicles: list[VehicleRecord]) -> ComparisonResult:
    vehicle = min(vehicles, key=lambda item: item.km_driven)
    value = f"{vehicle.km_driven:,} km"
    return f"Lowest kilometres: {vehicle.make} {vehicle.model} at {value}", (vehicle.make, vehicle.model, value)


def _highest_payload(vehicles: list[VehicleRecord]) -> ComparisonResult | None:
    known = [vehicle for vehicle in vehicles if vehicle.payload_kg is not None]
    if not known:
        return None

    vehicle = max(known, key=lambda item: item.payload_kg or 0)
    label, value = _payload(vehicle)
    heading = f"Highest {label.casefold()}: {vehicle.make} {vehicle.model} at {value}"
    checks = [vehicle.make, vehicle.model]
    if vehicle.payload_is_estimated:
        checks.append("estimated")
    checks.append(value)
    return heading, tuple(checks)


COMPARISON_RENDERERS: dict[str, Callable[[list[VehicleRecord]], ComparisonResult | None]] = {
    "best_match": _best_match,
    "cheapest": _cheapest,
    "lowest_mileage": _lowest_mileage,
    "highest_payload": _highest_payload,
}


def details_response(
    vehicles: list[VehicleRecord],
    fields: list[DetailField],
    comparison: str | None = None,
) -> GroundedResponse:
    facts: list[str] = []
    check_groups: list[tuple[str, ...]] = []
    display_sections: list[str] = []
    field_set = set(fields)
    details_by_vehicle: list[dict[DetailField, DetailValue]] = []

    for vehicle in vehicles:
        rendered = [_render_detail(vehicle, field) for field in fields]
        details_by_vehicle.append(dict(zip(fields, rendered, strict=True)))

        name = f"{vehicle.make} {vehicle.model}"
        checks = [f"{vehicle.make} {vehicle.model}"]
        for detail in rendered:
            checks.extend(detail.checks)

        facts.append(f"{name}: " + ", ".join(detail.fact for detail in rendered))
        check_groups.append(tuple(checks))
        details = "\n".join(f"- **{detail.display_label}:** {detail.display_value}" for detail in rendered)
        display_sections.append(f"#### {name}\n\n{details}")

    comparison_renderer = COMPARISON_RENDERERS.get(comparison or "")
    comparison_result = comparison_renderer(vehicles) if comparison_renderer else None

    if comparison_result:
        facts.append(comparison_result[0])
        check_groups.append(comparison_result[1])

    full_details = field_set == set(DetailField)
    if len(vehicles) > 1 and full_details:
        response = _multiple_detail_summary(vehicles, details_by_vehicle)
    else:
        response = " ".join(
            _detail_summary(vehicle, details)
            for vehicle, details in zip(vehicles, details_by_vehicle, strict=True)
        )
    if comparison_result:
        response += f" {comparison_result[0]}."
    if len(vehicles) > 1 and not full_details and ({DetailField.payload, DetailField.gvw} & field_set):
        response = "Compare the cargo weight and loading needs before deciding. " + response

    subject = "this vehicle" if len(vehicles) == 1 else f"these {len(vehicles)} vehicles"
    display = f"Here are the catalog details for {subject}.\n\n" + "\n\n".join(display_sections)
    if comparison_result:
        display = f"**{comparison_result[0]}**\n\n" + display
    return GroundedResponse(response, tuple(facts), tuple(check_groups), display)


def message_response(text: str) -> GroundedResponse:
    return GroundedResponse(text, (text,), ((text,),))


def catalog_options_response(options: dict[CatalogTopic, list[str]]) -> GroundedResponse:
    labels = {
        CatalogTopic.cities: "Available cities",
        CatalogTopic.vehicle_categories: "Vehicle categories",
        CatalogTopic.body_types: "Body types",
        CatalogTopic.fuels: "Fuel types",
        CatalogTopic.makes: "Makes",
        CatalogTopic.purposes: "Listed uses",
    }
    facts = tuple(
        f"{labels[topic]}: {', '.join(value.replace('_', ' ') for value in values)}"
        for topic, values in options.items()
    )
    checks = tuple(tuple(values) for values in options.values())
    return GroundedResponse(". ".join(facts) + ".", facts, checks)


def conversational_response(candidate: object, *, first_turn: bool, user_input: str = "") -> str:
    """Allow side conversation while rejecting ungrounded numeric vehicle claims."""
    if first_turn and re.fullmatch(r"\s*(?:hi|hello|hey|yo|namaste)[!.,?\s]*", user_input, re.IGNORECASE):
        return "Hey, I'm Vivi. Tell me what you need to transport, your budget, and where you're looking."

    response = candidate.strip() if isinstance(candidate, str) else ""
    has_ungrounded_value = bool(
        re.search(
            r"(?:₹|\bINR\b)\s*\d|\d[\d,.]*\s*(?:lakh|crore|km|kg|tons?|tonnes?)\b|\b(?:19|20)\d{2}\b",
            response,
            re.IGNORECASE,
        )
    )
    if not response or has_ungrounded_value:
        response = "I can help with commercial-vehicle searches and general questions about choosing one."

    if first_turn and "vivi" not in response.casefold():
        response = "Hi, I'm Vivi. " + response
    return " ".join(response.replace("**", "").replace("’", "'").replace("‑", "-").split())


def _normalized(text: str) -> str:
    text = text.casefold().replace("₹", "").replace("inr", "").replace("rupees", "").replace("lakh", "l")
    return re.sub(r"[^a-z0-9.]", "", text)


def _contains_checks_in_order(response: str, checks: tuple[tuple[str, ...], ...]) -> bool:
    normalized = _normalized(response)
    cursor = 0
    for group in checks:
        for expected in group:
            position = normalized.find(_normalized(expected), cursor)
            if position < 0:
                return False
            cursor = position + len(_normalized(expected))
    return True


def natural_response(
    candidate: object,
    grounded: GroundedResponse,
    *,
    first_turn: bool,
) -> str:
    """Accept natural framing only when every catalog fact remains unchanged."""
    response = candidate.strip() if isinstance(candidate, str) else ""

    facts_unchanged = _contains_checks_in_order(response, grounded.checks)
    allowed_numbers = set(re.findall(r"\d+(?:[.,]\d+)*", " ".join(grounded.facts)))
    allowed_numbers.update(str(index) for index in range(1, len(grounded.checks) + 1))
    response_numbers = set(re.findall(r"\d+(?:[.,]\d+)*", response))
    if not response or not facts_unchanged or not response_numbers <= allowed_numbers:
        response = grounded.fallback

    if first_turn and "vivi" not in response.casefold():
        warm_intro = "Hi, I'm Vivi. I'll help you find the right used truck. "
        response = warm_intro + response

    return " ".join(response.replace("**", "").split())
