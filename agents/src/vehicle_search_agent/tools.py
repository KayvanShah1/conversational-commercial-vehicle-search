from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Annotated, Literal, get_args

from pydantic import Field
from vehicle_search_utils import OperationLogContext, get_logger

from agents import RunContextWrapper, function_tool
from vehicle_search_agent.models import (
    AgentAction,
    CatalogTopic,
    ConversationState,
    DetailField,
    SearchField,
    SlotPatch,
    VehicleCategory,
    VehicleSearchResult,
    WeightClass,
    merge_slot_patch,
)
from vehicle_search_agent.response import (
    GroundedResponse,
    catalog_options_response,
    details_response,
    message_response,
    search_response,
)
from vehicle_search_agent.search import get_catalog_options, get_vehicles, search_catalog
from vehicle_search_agent.settings import settings

logger = get_logger("VehicleSearchTools")

BodyType = Literal["open", "flatbed", "box", "container", "tipper", "tanker", "reefer"]
Fuel = Literal["CNG", "Diesel"]
Purpose = Literal[
    "agriculture",
    "city_delivery",
    "cold_chain",
    "construction",
    "ecommerce",
    "fmcg",
    "fuel_transport",
    "heavy_delivery",
    "industrial_goods",
    "last_mile",
    "logistics",
    "long_haul",
    "market_transport",
    "mining",
    "parcel_delivery",
    "regional_delivery",
    "roadwork",
    "vegetable_delivery",
    "water_transport",
]


@dataclass
class AgentContext:
    state: ConversationState
    current_input: str = ""
    action: AgentAction = AgentAction.conversation
    last_search_result: VehicleSearchResult | None = None
    catalog_ms: float | None = None
    grounded_response: GroundedResponse | None = None
    response_ms: float | None = None
    understanding_ms: float | None = None
    llm_operation: OperationLogContext | None = None
    tool_failures: int = 0

    def reset_turn(self) -> None:
        self.current_input = ""
        self.action = AgentAction.conversation
        self.last_search_result = None
        self.catalog_ms = None
        self.grounded_response = None
        self.response_ms = None
        self.understanding_ms = None
        self.llm_operation = None
        self.tool_failures = 0


def retry_tool_error(ctx: RunContextWrapper[AgentContext], error: Exception) -> str:
    """Return invalid arguments to the model for at most three self-correction attempts."""
    ctx.context.tool_failures += 1
    logger.warning(
        "tool_input_rejected",
        extra={"attempt": ctx.context.tool_failures, "error_type": type(error).__name__, "error": str(error)},
    )
    return f"Tool arguments were invalid. Correct them using the declared schema and retry. Validation: {error}"


def _mentioned(value: str, text: str) -> bool:
    return re.sub(r"[^a-z0-9]", "", value.casefold()) in re.sub(r"[^a-z0-9]", "", text.casefold())


def _explicit(options: tuple[str, ...], text: str) -> str | None:
    return next((option for option in options if _mentioned(option, text)), None)


def _rephrase_request(response: GroundedResponse, *, first_turn: bool) -> str:
    facts = "\n".join(f"- {fact}" for fact in response.facts)
    introduction = " Begin with a short, warm introduction as Vivi." if first_turn else ""
    return (
        "Write one concise, natural reply. Preserve every catalog value and key label below, "
        f"but connect and rephrase them naturally. Mention each vehicle once. Do not add facts or numbers.{introduction}\n\n"
        f"Grounded facts:\n{facts}"
    )


def _set_response(context: AgentContext, response: GroundedResponse) -> str:
    context.grounded_response = response
    return _rephrase_request(response, first_turn=context.state.turn_number == 1)


@function_tool(
    strict_mode=False,
    timeout=settings.agent_runtime.tool_timeout_seconds,
    timeout_behavior="raise_exception",
    failure_error_function=retry_tool_error,
)
async def search_vehicles(
    ctx: RunContextWrapper[AgentContext],
    budget_min: Annotated[int, Field(ge=0, description="Minimum INR budget stated by the user")] | None = None,
    budget_max: Annotated[
        int,
        Field(ge=0, description="Maximum INR budget stated by the user; convert 20 lakh to 2000000"),
    ]
    | None = None,
    body_type: Annotated[BodyType, Field(description="Physical cargo body stated by the user; do not infer it")]
    | None = None,
    fuel: Annotated[Fuel, Field(description="Fuel stated by the user; do not infer it")] | None = None,
    city: Annotated[str, Field(description="Listing city; for a route use its origin city")] | None = None,
    purpose: Annotated[Purpose, Field(description="Closest intended work or route type; ranking signal only")]
    | None = None,
    category: Annotated[VehicleCategory, Field(description="Construction category named by the user")] | None = None,
    size: Annotated[
        WeightClass,
        Field(description="Closest stated or implied size; chhota/small means light, bada/heavy means heavy"),
    ]
    | None = None,
    make: str | None = None,
    model: str | None = None,
    payload_min_kg: Annotated[int, Field(ge=0, description="Minimum payload only when a number is stated")]
    | None = None,
    gvw_min_kg: Annotated[int, Field(ge=0, description="Minimum GVW only when a number is stated")] | None = None,
    papers_verified: bool | None = None,
    clear_fields: list[SearchField] | None = None,
    more_results: Annotated[bool, Field(description="True only when the user asks for more or next options")] = False,
) -> str:
    """Search stated constraints. Infer size and purpose; category, body, and fuel must be explicit.

    Valid category values: mini_truck, pickup, rigid_truck. Valid size values:
    light, intermediate, medium, heavy. Valid body values: open, flatbed, box,
    container, tipper, tanker, reefer. Valid fuel values: CNG, Diesel.
    Valid purposes: agriculture, city_delivery, cold_chain, construction,
    ecommerce, fmcg, fuel_transport, heavy_delivery, industrial_goods,
    last_mile, logistics, long_haul, market_transport, mining, parcel_delivery,
    regional_delivery, roadwork, vegetable_delivery, water_transport.
    """
    body_type = _explicit(get_args(BodyType), ctx.context.current_input)
    fuel = _explicit(get_args(Fuel), ctx.context.current_input)
    category = _explicit(tuple(value.value for value in VehicleCategory), ctx.context.current_input)
    more_results = more_results or bool(
        re.search(r"\b(?:more|next|another)\s+(?:options?|vehicles?|results?)\b", ctx.context.current_input, re.IGNORECASE)
    )
    patch = SlotPatch(
        budget_min=budget_min,
        budget_max=budget_max,
        body_type=body_type,
        fuel=fuel,
        city=city,
        purpose=purpose,
        vehicle_category=category,
        weight_class=size,
        make=make,
        model=model,
        payload_min_kg=payload_min_kg,
        gvw_min_kg=gvw_min_kg,
        papers_verified=papers_verified,
        clear_fields=clear_fields or [],
    )
    context = ctx.context
    context.action = AgentAction.search

    filters, changed_fields = merge_slot_patch(context.state.active_filters, patch)
    excluded_ids = context.state.shown_result_ids if more_results else []
    result = await asyncio.to_thread(search_catalog, filters, changed_fields, excluded_ids)

    context.state.active_filters = filters
    context.state.last_result_ids = [item.vehicle.listing_id for item in result.vehicles]
    if more_results:
        context.state.shown_result_ids.extend(context.state.last_result_ids)
    else:
        context.state.shown_result_ids = list(context.state.last_result_ids)
    context.state.selected_listing_id = None
    context.last_search_result = result
    return _set_response(context, search_response(result))


@function_tool(
    strict_mode=False,
    timeout=settings.agent_runtime.tool_timeout_seconds,
    timeout_behavior="raise_exception",
    failure_error_function=retry_tool_error,
)
async def get_vehicle_details(
    ctx: RunContextWrapper[AgentContext],
    fields: Annotated[list[DetailField], Field(min_length=1, max_length=14)] | None = None,
    result_number: Annotated[int, Field(ge=1, le=3)] | None = None,
    all_details: Annotated[bool, Field(description="True when the user asks for every available vehicle attribute")] = False,
) -> str:
    """Read facts for previous results; omit result_number for these/all results.

    Valid fields: year, price, km_driven, fuel, payload, gvw, body_type, city,
    papers_verified, condition, purpose_tags, vehicle_category, weight_class,
    axle_count. Set all_details=true for every available attribute. For capability
    questions use payload, gvw, body_type, and purpose_tags.
    Never call this once per result when the user asks about all results.
    """
    context = ctx.context
    context.action = AgentAction.details
    state = context.state

    if all_details or re.search(r"\b(?:all|full|every)\s+(?:the\s+)?details?\b", context.current_input, re.IGNORECASE):
        fields = list(DetailField)
    elif not fields:
        return _set_response(context, message_response("Which vehicle details would you like?"))

    if not state.last_result_ids:
        return _set_response(context, message_response("Please search for vehicles first."))

    plural_reference = re.search(
        r"\b(?:these|those|they|them|options|vehicles|results|inmein|ye|yeh)\b|\ball\s+(?:three|\d+)\b",
        context.current_input,
        re.IGNORECASE,
    )
    if plural_reference:
        listing_ids = state.last_result_ids
    elif result_number is not None:
        if result_number > len(state.last_result_ids):
            return _set_response(context, message_response("I don't have that result number in the previous search."))
        listing_ids = [state.last_result_ids[result_number - 1]]
    elif state.selected_listing_id:
        listing_ids = [state.selected_listing_id]
    else:
        listing_ids = state.last_result_ids

    vehicles, context.catalog_ms = await asyncio.to_thread(get_vehicles, listing_ids)
    if not vehicles:
        return _set_response(
            context,
            message_response("Those previous vehicles are no longer available in the catalog."),
        )

    state.selected_listing_id = listing_ids[0] if len(listing_ids) == 1 else None
    return _set_response(context, details_response(vehicles, fields, context.current_input))


@function_tool(
    strict_mode=False,
    timeout=settings.agent_runtime.tool_timeout_seconds,
    timeout_behavior="raise_exception",
    failure_error_function=retry_tool_error,
)
async def list_catalog_options(
    ctx: RunContextWrapper[AgentContext],
    include_cities: bool = False,
    include_categories: bool = False,
    include_body_types: bool = False,
    include_fuels: bool = False,
    include_makes: bool = False,
) -> str:
    """List distinct cities, vehicle categories, body types, fuels, or makes available in the catalog."""
    context = ctx.context
    context.action = AgentAction.catalog_options
    requested = {
        CatalogTopic.cities: include_cities,
        CatalogTopic.vehicle_categories: include_categories,
        CatalogTopic.body_types: include_body_types,
        CatalogTopic.fuels: include_fuels,
        CatalogTopic.makes: include_makes,
    }
    topics = [topic for topic, included in requested.items() if included]
    if not topics:
        return _set_response(context, message_response("Which catalog options would you like to know about?"))

    options, context.catalog_ms = await asyncio.to_thread(get_catalog_options, topics)
    return _set_response(context, catalog_options_response(options))
