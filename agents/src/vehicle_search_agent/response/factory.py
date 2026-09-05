from vehicle_search_agent.models import CatalogTopic, DetailField, RankedVehicle, VehicleRecord, VehicleSearchResult
from vehicle_search_agent.response.comparisons import compare_vehicles
from vehicle_search_agent.response.details import (
    format_price,
    render_detail,
)
from vehicle_search_agent.response.models import DetailValue, GroundedResponse
from vehicle_search_agent.response.summaries import detail_markdown, detail_summary, multiple_detail_summary


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
            f"{ranked.vehicle.make} {ranked.vehicle.model} at {format_price(ranked.vehicle.price_inr)}, with {reason}"
            for ranked, reason in zip(result.vehicles, reasons, strict=True)
        ]
        checks = tuple(
            (
                f"{ranked.vehicle.make} {ranked.vehicle.model}",
                format_price(ranked.vehicle.price_inr),
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
    details_by_vehicle: list[dict[DetailField, DetailValue]] = []

    for vehicle in vehicles:
        rendered = [render_detail(vehicle, field) for field in fields]
        details_by_vehicle.append(dict(zip(fields, rendered, strict=True)))

        name = f"{vehicle.make} {vehicle.model}"
        checks = [f"{vehicle.make} {vehicle.model}"]
        for detail in rendered:
            checks.extend(detail.checks)

        facts.append(f"{name}: " + ", ".join(detail.fact for detail in rendered))
        check_groups.append(tuple(checks))
        display_sections.append(detail_markdown(vehicle, rendered))

    comparison_result = compare_vehicles(vehicles, comparison)

    if comparison_result:
        facts.append(comparison_result[0])
        check_groups.append(comparison_result[1])

    full_details = field_set == set(DetailField)
    if len(vehicles) > 1 and full_details:
        response = multiple_detail_summary(vehicles, details_by_vehicle)
    else:
        response = " ".join(
            detail_summary(vehicle, details) for vehicle, details in zip(vehicles, details_by_vehicle, strict=True)
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
