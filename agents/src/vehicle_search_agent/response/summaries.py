from vehicle_search_agent.models import DetailField, VehicleRecord
from vehicle_search_agent.response.details import join_naturally
from vehicle_search_agent.response.models import DetailValue

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


def detail_summary(vehicle: VehicleRecord, details: dict[DetailField, DetailValue]) -> str:
    name = f"{vehicle.make} {vehicle.model}"
    sentences = [sentence] if (sentence := _identity_sentence(vehicle, details)) else []
    for group in SPOKEN_FIELD_GROUPS:
        clauses = [detail.spoken_clause for field in group if (detail := details.get(field)) and detail.spoken_clause]
        if clauses:
            subject = "It" if sentences else name
            sentences.append(f"{subject} {join_naturally(clauses)}.")

    if source := details.get(DetailField.spec_source_url):
        sentences.append(f"The specification source for {name} is {source.checks[0]}.")
    return " ".join(sentences)


def multiple_detail_summary(
    vehicles: list[VehicleRecord],
    details_by_vehicle: list[dict[DetailField, DetailValue]],
) -> str:
    sentences = [f"I found {len(vehicles)} matching listings."]
    for vehicle, details in zip(vehicles, details_by_vehicle, strict=True):
        name = f"{vehicle.make} {vehicle.model}"
        qualifiers = [
            detail.display_value for field in (DetailField.year, DetailField.city) if (detail := details.get(field))
        ]
        subject = f"The {' '.join(qualifiers)} {name} listing" if qualifiers else name
        highlights = [
            detail.spoken_clause
            for field in (DetailField.price, DetailField.km_driven, DetailField.payload, DetailField.gvw)
            if (detail := details.get(field)) and detail.spoken_clause
        ]
        sentences.append(f"{subject} {join_naturally(highlights)}." if highlights else f"{subject} is included.")

    first_details = details_by_vehicle[0]
    if DetailField.fuel in first_details and len({vehicle.fuel for vehicle in vehicles}) == 1:
        sentences.append(f"All run on {first_details[DetailField.fuel].display_value}.")
    if DetailField.papers_verified in first_details and all(vehicle.papers_verified for vehicle in vehicles):
        sentences.append("All have verified papers.")
    sentences.append("The full specifications and source links are shown on screen.")
    return " ".join(sentences)


def detail_markdown(vehicle: VehicleRecord, rendered: list[DetailValue]) -> str:
    name = f"{vehicle.make} {vehicle.model}"
    details = "\n".join(f"- **{detail.display_label}:** {detail.display_value}" for detail in rendered)
    return f"#### {name}\n\n{details}"
