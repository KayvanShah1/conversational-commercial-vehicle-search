import asyncio
import re
from typing import Annotated, Literal

from pydantic import Field

from agents import RunContextWrapper, function_tool
from vehicle_search_agent.models import AgentAction, DetailField, VehicleRecord
from vehicle_search_agent.response import details_response, message_response
from vehicle_search_agent.search import get_vehicles
from vehicle_search_agent.settings import settings
from vehicle_search_agent.tools.context import AgentContext, logger, retry_tool_error, set_response

DetailScope = Literal["one", "all"]
DetailMode = Literal[
    "facts", "capability", "all_details", "best_match", "cheapest", "lowest_mileage", "highest_payload"
]


def mentioned(value: str, text: str) -> bool:
    return re.sub(r"[^a-z0-9]", "", value.casefold()) in re.sub(r"[^a-z0-9]", "", text.casefold())


def named_vehicles(vehicles: list[VehicleRecord], text: str) -> list[VehicleRecord]:
    words = set(re.findall(r"[a-z0-9]+", text.casefold()))
    matches = []
    for vehicle in vehicles:
        model_words = set(re.findall(r"[a-z0-9]+", vehicle.model.casefold())) - {"cng", "diesel"}
        if mentioned(vehicle.make, text) or model_words & words:
            matches.append(vehicle)
    return matches


@function_tool(
    strict_mode=False,
    timeout=settings.agent_runtime.tool_timeout_seconds,
    timeout_behavior="raise_exception",
    failure_error_function=retry_tool_error,
)
async def get_vehicle_details(
    ctx: RunContextWrapper[AgentContext],
    scope: Annotated[DetailScope, Field(description="one prior result or all current results")],
    mode: Annotated[
        DetailMode,
        Field(
            description=(
                "facts for named fields; capability for can-carry questions; all_details only for "
                "explicit requests for every detail; otherwise choose the requested comparison mode"
            )
        ),
    ] = "facts",
    fields: Annotated[list[DetailField], Field(min_length=1, max_length=15)] | None = None,
    result_number: Annotated[int, Field(ge=1, le=3)] | None = None,
) -> str:
    """Read or compare grounded facts from previously returned results.

    Use this only when the turn does not add or change a search constraint. A
    comparison containing a new preference belongs to search_vehicles, even if
    the current results already appear to satisfy it. Use
    scope=all for plural references and comparisons. For one result, pass its
    result_number when known; a named make or model can otherwise be resolved
    against prior results. Use mode=all_details for every available attribute.
    For capability questions request payload, gvw, body_type, and purpose_tags;
    for brochures request spec_source_url. Never call this once per result for
    scope=all. Accepted fields and modes are declared in the tool schema.
    """
    logger.info("tool_called", extra={"tool": "get_vehicle_details"})
    context = ctx.context
    context.action = AgentAction.details
    state = context.state

    comparison_fields = {
        "best_match": list(DetailField),
        "cheapest": [DetailField.price],
        "lowest_mileage": [DetailField.km_driven],
        "highest_payload": [DetailField.payload],
    }
    if mode == "capability":
        fields = [DetailField.payload, DetailField.gvw, DetailField.body_type, DetailField.purpose_tags]
    elif mode == "all_details":
        fields = list(DetailField)
    elif mode in comparison_fields:
        fields = comparison_fields[mode]
    elif not fields:
        return set_response(context, message_response("Which vehicle details would you like?"))

    if not state.last_result_ids:
        return set_response(context, message_response("Please search for vehicles first."))

    vehicles: list[VehicleRecord] | None = None
    if scope == "all":
        listing_ids = list(state.last_result_ids)
    elif result_number is not None:
        if result_number > len(state.last_result_ids):
            return set_response(context, message_response("I don't have that result number in the previous search."))
        listing_ids = [state.last_result_ids[result_number - 1]]
    elif state.selected_listing_id:
        listing_ids = [state.selected_listing_id]
    else:
        candidates, context.catalog_ms = await asyncio.to_thread(get_vehicles, state.last_result_ids)
        vehicles = named_vehicles(candidates, context.current_input)
        if not vehicles:
            return set_response(
                context,
                message_response("Which previous result do you mean: first, second, or third?"),
            )
        listing_ids = [vehicle.listing_id for vehicle in vehicles]

    if vehicles is None:
        vehicles, context.catalog_ms = await asyncio.to_thread(get_vehicles, listing_ids)
    if not vehicles:
        return set_response(
            context,
            message_response("Those previous vehicles are no longer available in the catalog."),
        )

    state.selected_listing_id = listing_ids[0] if len(listing_ids) == 1 else None
    comparison = mode if mode in comparison_fields else None
    return set_response(context, details_response(vehicles, fields, comparison))
