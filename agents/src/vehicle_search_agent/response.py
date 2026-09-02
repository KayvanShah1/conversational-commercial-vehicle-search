from __future__ import annotations

import re
from dataclasses import dataclass

from vehicle_search_agent.models import CatalogTopic, DetailField, RankedVehicle, VehicleRecord, VehicleSearchResult


@dataclass(frozen=True)
class GroundedResponse:
    fallback: str
    facts: tuple[str, ...]
    checks: tuple[tuple[str, ...], ...]


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


def details_response(vehicles: list[VehicleRecord], fields: list[DetailField], question: str = "") -> GroundedResponse:
    facts: list[str] = []
    check_groups: list[tuple[str, ...]] = []

    for vehicle in vehicles:
        values: list[str] = []
        checks = [f"{vehicle.make} {vehicle.model}"]
        for field in fields:
            match field:
                case DetailField.year:
                    values.append(f"year {vehicle.year}")
                    checks.append(str(vehicle.year))
                case DetailField.price:
                    values.append(f"price {_price(vehicle.price_inr)}")
                    checks.append(_price(vehicle.price_inr))
                case DetailField.km_driven:
                    values.append(f"{vehicle.km_driven:,} km")
                    checks.append(str(vehicle.km_driven))
                case DetailField.fuel:
                    values.append(f"fuel {vehicle.fuel}")
                    checks.append(vehicle.fuel)
                case DetailField.payload:
                    payload = f"{vehicle.payload_kg} kg" if vehicle.payload_kg is not None else "not listed"
                    values.append(f"payload {payload}")
                    checks.append(str(vehicle.payload_kg) if vehicle.payload_kg is not None else "not listed")
                case DetailField.gvw:
                    values.append(f"GVW {vehicle.gvw_kg} kg")
                    checks.append(str(vehicle.gvw_kg))
                case DetailField.body_type:
                    values.append(f"body type {vehicle.body_type}")
                    checks.append(vehicle.body_type)
                case DetailField.city:
                    values.append(f"city {vehicle.city}")
                    checks.append(vehicle.city)
                case DetailField.papers_verified:
                    values.append("papers verified" if vehicle.papers_verified else "papers not verified")
                    checks.append("verified" if vehicle.papers_verified else "not verified")
                case DetailField.condition:
                    values.append(f"condition {vehicle.condition}")
                    checks.append(vehicle.condition)
                case DetailField.purpose_tags:
                    purposes = ", ".join(tag.replace("_", " ") for tag in vehicle.purpose_tags)
                    values.append(f"listed uses {purposes}")
                    checks.extend(tag.replace("_", " ") for tag in vehicle.purpose_tags)
                case DetailField.vehicle_category:
                    category = vehicle.vehicle_category.replace("_", " ")
                    values.append(f"category {category}")
                    checks.append(category)
                case DetailField.weight_class:
                    values.append(f"size class {vehicle.weight_class}")
                    checks.append(vehicle.weight_class)
                case DetailField.axle_count:
                    values.append(f"axles {vehicle.axle_count}")
                    checks.append(str(vehicle.axle_count))
                case DetailField.spec_source_url:
                    values.append(f"specification source {vehicle.spec_source_url}")
                    checks.append(vehicle.spec_source_url)

        facts.append(f"{vehicle.make} {vehicle.model}: " + ", ".join(values))
        check_groups.append(tuple(checks))

    question = question.casefold()
    comparison: tuple[str, tuple[str, ...]] | None = None
    if "cheapest" in question:
        vehicle = min(vehicles, key=lambda item: item.price_inr)
        value = _price(vehicle.price_inr)
        comparison = (f"Cheapest: {vehicle.make} {vehicle.model} at {value}", (vehicle.make, vehicle.model, value))
    elif "lowest" in question and DetailField.km_driven in fields:
        vehicle = min(vehicles, key=lambda item: item.km_driven)
        value = f"{vehicle.km_driven:,} km"
        comparison = (f"Lowest kilometres: {vehicle.make} {vehicle.model} at {value}", (vehicle.make, vehicle.model, value))
    elif re.search(r"\b(?:highest|most)\b", question) and DetailField.payload in fields:
        known = [vehicle for vehicle in vehicles if vehicle.payload_kg is not None]
        if known:
            vehicle = max(known, key=lambda item: item.payload_kg or 0)
            value = f"{vehicle.payload_kg} kg"
            comparison = (f"Highest payload: {vehicle.make} {vehicle.model} at {value}", (vehicle.make, vehicle.model, value))

    if comparison:
        facts.append(comparison[0])
        check_groups.append(comparison[1])

    response = ". ".join(facts) + "."
    if len(vehicles) > 1 and ({DetailField.payload, DetailField.gvw} & set(fields)):
        response = "Confirm the cargo weight and loading needs before deciding. Catalog specifications: " + response
    return GroundedResponse(response, tuple(facts), tuple(check_groups))


def message_response(text: str) -> GroundedResponse:
    return GroundedResponse(text, (text,), ((text,),))


def catalog_options_response(options: dict[CatalogTopic, list[str]]) -> GroundedResponse:
    labels = {
        CatalogTopic.cities: "Available cities",
        CatalogTopic.vehicle_categories: "Vehicle categories",
        CatalogTopic.body_types: "Body types",
        CatalogTopic.fuels: "Fuel types",
        CatalogTopic.makes: "Makes",
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
