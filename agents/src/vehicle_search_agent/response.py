from __future__ import annotations

import re
from dataclasses import dataclass

from vehicle_search_agent.models import CatalogTopic, DetailField, RankedVehicle, VehicleRecord, VehicleSearchResult


@dataclass(frozen=True)
class GroundedResponse:
    fallback: str
    facts: tuple[str, ...]
    checks: tuple[tuple[str, ...], ...]
    display_markdown: str | None = None


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


def _detail_summary(vehicle: VehicleRecord, fields: set[DetailField]) -> str:
    name = f"{vehicle.make} {vehicle.model}"
    sentences: list[str] = []
    category = vehicle.vehicle_category.replace("_", " ")
    if DetailField.year in fields and DetailField.vehicle_category in fields:
        introduction = f"{name} is a {vehicle.year} model in the {category} category"
    elif DetailField.year in fields:
        introduction = f"{name} is a {vehicle.year} model"
    elif DetailField.vehicle_category in fields:
        introduction = f"{name} is a {category}"
    else:
        introduction = ""
    if DetailField.body_type in fields:
        article = "an" if vehicle.body_type[:1].casefold() in "aeiou" else "a"
        introduction += (
            f" and has {article} {vehicle.body_type} body"
            if introduction
            else f"{name} has {article} {vehicle.body_type} body"
        )
    if introduction:
        sentences.append(introduction + ".")
    if DetailField.city in fields:
        subject = "It" if sentences else name
        sentences.append(f"{subject} is listed in {vehicle.city}.")

    running = []
    if DetailField.price in fields:
        running.append(f"costs {_price(vehicle.price_inr)}")
    if DetailField.km_driven in fields:
        running.append(f"has covered {vehicle.km_driven:,} km")
    if DetailField.fuel in fields:
        running.append(f"runs on {vehicle.fuel}")
    if running:
        subject = "It" if sentences else name
        sentences.append(f"{subject} {_join_naturally(running)}.")

    capacity = []
    if DetailField.payload in fields:
        label, payload = _payload(vehicle)
        article = "an" if vehicle.payload_is_estimated else "a"
        capacity.append(f"has {article} {label.casefold()} of {payload}")
    if DetailField.gvw in fields:
        capacity.append(f"has a GVW of {vehicle.gvw_kg:,} kg")
    if DetailField.axle_count in fields:
        capacity.append(f"has {vehicle.axle_count} axles")
    if capacity:
        subject = "It" if sentences else name
        sentences.append(f"{subject} {_join_naturally(capacity)}.")

    status = []
    if DetailField.papers_verified in fields:
        status.append("has verified papers" if vehicle.papers_verified else "does not have verified papers")
    if DetailField.condition in fields:
        status.append(f"is in {vehicle.condition} condition")
    if DetailField.weight_class in fields:
        status.append(f"is in the {vehicle.weight_class} weight class")
    if status:
        subject = "It" if sentences else name
        sentences.append(f"{subject} {_join_naturally(status)}.")

    if DetailField.purpose_tags in fields:
        purposes = [tag.replace("_", " ") for tag in vehicle.purpose_tags]
        subject = "It" if sentences else name
        sentences.append(f"{subject} is listed for {_join_naturally(purposes)}.")
    if DetailField.spec_source_url in fields:
        sentences.append(f"The specification source for {name} is {vehicle.spec_source_url}.")
    return " ".join(sentences)


def _multiple_detail_summary(vehicles: list[VehicleRecord], fields: set[DetailField]) -> str:
    sentences = [f"I found {len(vehicles)} matching listings."]
    for vehicle in vehicles:
        name = f"{vehicle.make} {vehicle.model}"
        qualifiers = []
        if DetailField.year in fields:
            qualifiers.append(str(vehicle.year))
        if DetailField.city in fields:
            qualifiers.append(vehicle.city)
        subject = f"The {' '.join(qualifiers)} {name} listing" if qualifiers else name

        highlights = []
        if DetailField.price in fields:
            highlights.append(f"costs {_price(vehicle.price_inr)}")
        if DetailField.km_driven in fields:
            highlights.append(f"has covered {vehicle.km_driven:,} km")
        if DetailField.payload in fields:
            label, payload = _payload(vehicle)
            article = "an" if vehicle.payload_is_estimated else "a"
            highlights.append(f"has {article} {label.casefold()} of {payload}")
        if DetailField.gvw in fields:
            highlights.append(f"has a GVW of {vehicle.gvw_kg:,} kg")
        sentences.append(f"{subject} {_join_naturally(highlights)}." if highlights else f"{subject} is included.")

    if DetailField.fuel in fields and len({vehicle.fuel for vehicle in vehicles}) == 1:
        sentences.append(f"All run on {vehicles[0].fuel}.")
    if DetailField.papers_verified in fields and all(vehicle.papers_verified for vehicle in vehicles):
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


def details_response(
    vehicles: list[VehicleRecord],
    fields: list[DetailField],
    comparison: str | None = None,
) -> GroundedResponse:
    facts: list[str] = []
    check_groups: list[tuple[str, ...]] = []
    display_sections: list[str] = []
    field_set = set(fields)

    for vehicle in vehicles:
        values: list[str] = []
        display_values: list[tuple[str, str]] = []
        checks = [f"{vehicle.make} {vehicle.model}"]
        for field in fields:
            match field:
                case DetailField.year:
                    values.append(f"year {vehicle.year}")
                    display_values.append(("Year", str(vehicle.year)))
                    checks.append(str(vehicle.year))
                case DetailField.price:
                    values.append(f"price {_price(vehicle.price_inr)}")
                    display_values.append(("Price", _price(vehicle.price_inr)))
                    checks.append(_price(vehicle.price_inr))
                case DetailField.km_driven:
                    values.append(f"{vehicle.km_driven:,} km")
                    display_values.append(("Kilometres driven", f"{vehicle.km_driven:,} km"))
                    checks.append(str(vehicle.km_driven))
                case DetailField.fuel:
                    values.append(f"fuel {vehicle.fuel}")
                    display_values.append(("Fuel", vehicle.fuel))
                    checks.append(vehicle.fuel)
                case DetailField.payload:
                    label, payload = _payload(vehicle)
                    values.append(f"{label.casefold()} {payload}")
                    display_values.append((label, payload))
                    if vehicle.payload_is_estimated:
                        checks.append("estimated")
                    checks.append(str(vehicle.payload_kg) if vehicle.payload_kg is not None else "not listed")
                case DetailField.gvw:
                    gvw = f"{vehicle.gvw_kg:,} kg"
                    values.append(f"GVW {gvw}")
                    display_values.append(("GVW", gvw))
                    checks.append(str(vehicle.gvw_kg))
                case DetailField.body_type:
                    values.append(f"body type {vehicle.body_type}")
                    display_values.append(("Body", vehicle.body_type.title()))
                    checks.append(vehicle.body_type)
                case DetailField.city:
                    values.append(f"city {vehicle.city}")
                    display_values.append(("City", vehicle.city))
                    checks.append(vehicle.city)
                case DetailField.papers_verified:
                    papers = "Verified" if vehicle.papers_verified else "Not verified"
                    values.append(f"papers {papers.casefold()}")
                    display_values.append(("Papers", papers))
                    checks.append("verified" if vehicle.papers_verified else "not verified")
                case DetailField.condition:
                    values.append(f"condition {vehicle.condition}")
                    display_values.append(("Condition", vehicle.condition.title()))
                    checks.append(vehicle.condition)
                case DetailField.purpose_tags:
                    purposes = ", ".join(tag.replace("_", " ") for tag in vehicle.purpose_tags)
                    values.append(f"listed uses {purposes}")
                    display_values.append(("Listed uses", purposes))
                    checks.extend(tag.replace("_", " ") for tag in vehicle.purpose_tags)
                case DetailField.vehicle_category:
                    category = vehicle.vehicle_category.replace("_", " ")
                    values.append(f"category {category}")
                    display_values.append(("Category", category.title()))
                    checks.append(category)
                case DetailField.weight_class:
                    values.append(f"size class {vehicle.weight_class}")
                    display_values.append(("Weight class", vehicle.weight_class.title()))
                    checks.append(vehicle.weight_class)
                case DetailField.axle_count:
                    values.append(f"axles {vehicle.axle_count}")
                    display_values.append(("Axles", str(vehicle.axle_count)))
                    checks.append(str(vehicle.axle_count))
                case DetailField.spec_source_url:
                    values.append(f"specification source {vehicle.spec_source_url}")
                    display_values.append(
                        ("Specification source", f"[View manufacturer specifications]({vehicle.spec_source_url})")
                    )
                    checks.append(vehicle.spec_source_url)

        name = f"{vehicle.make} {vehicle.model}"
        facts.append(f"{name}: " + ", ".join(values))
        check_groups.append(tuple(checks))
        details = "\n".join(f"- **{label}:** {value}" for label, value in display_values)
        display_sections.append(f"#### {name}\n\n{details}")

    comparison_result: tuple[str, tuple[str, ...]] | None = None
    if comparison == "best_match":
        vehicle = vehicles[0]
        comparison_result = (f"Best match: {vehicle.make} {vehicle.model}", (vehicle.make, vehicle.model))
    elif comparison == "cheapest":
        vehicle = min(vehicles, key=lambda item: item.price_inr)
        value = _price(vehicle.price_inr)
        comparison_result = (
            f"Cheapest: {vehicle.make} {vehicle.model} at {value}",
            (vehicle.make, vehicle.model, value),
        )
    elif comparison == "lowest_mileage":
        vehicle = min(vehicles, key=lambda item: item.km_driven)
        value = f"{vehicle.km_driven:,} km"
        comparison_result = (
            f"Lowest kilometres: {vehicle.make} {vehicle.model} at {value}",
            (vehicle.make, vehicle.model, value),
        )
    elif comparison == "highest_payload":
        known = [vehicle for vehicle in vehicles if vehicle.payload_kg is not None]
        if known:
            vehicle = max(known, key=lambda item: item.payload_kg or 0)
            label, value = _payload(vehicle)
            heading = f"Highest {label.casefold()}: {vehicle.make} {vehicle.model} at {value}"
            checks = [vehicle.make, vehicle.model]
            if vehicle.payload_is_estimated:
                checks.append("estimated")
            checks.append(value)
            comparison_result = (heading, tuple(checks))

    if comparison_result:
        facts.append(comparison_result[0])
        check_groups.append(comparison_result[1])

    if len(vehicles) > 1 and len(fields) > 6:
        response = _multiple_detail_summary(vehicles, field_set)
    else:
        response = " ".join(_detail_summary(vehicle, field_set) for vehicle in vehicles)
    if comparison_result:
        response += f" {comparison_result[0]}."
    if len(vehicles) > 1 and len(fields) <= 6 and ({DetailField.payload, DetailField.gvw} & field_set):
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
