import asyncio
import re
from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import Field
from vehicle_search_utils import OperationLogContext, get_logger

from agents import RunContextWrapper, function_tool
from vehicle_search_agent.models import (
    AgentAction,
    BodyType,
    CatalogTopic,
    ConversationState,
    DetailField,
    FuelType,
    PurposeTag,
    SearchField,
    SearchFilters,
    SlotPatch,
    VehicleCategory,
    VehicleRecord,
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

SearchMode = Literal["new", "refine", "more"]
DetailScope = Literal["one", "all"]
DetailMode = Literal[
    "facts", "capability", "all_details", "best_match", "cheapest", "lowest_mileage", "highest_payload"
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
    llm_list_cost_usd: float = 0.0
    pricing_complete: bool = True
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
        self.llm_list_cost_usd = 0.0
        self.pricing_complete = True
        self.tool_failures = 0


def retry_tool_error(ctx: RunContextWrapper[AgentContext], error: Exception) -> str:
    """Return invalid arguments to the model for at most three self-correction attempts."""
    ctx.context.tool_failures += 1
    logger.warning(
        "tool_input_rejected",
        extra={
            "tool": getattr(ctx, "tool_name", "unknown"),
            "attempt": ctx.context.tool_failures,
            "error_type": type(error).__name__,
            "error": str(error),
        },
    )
    return f"Tool arguments were invalid. Correct them using the declared schema and retry. Validation: {error}"


def _mentioned(value: str, text: str) -> bool:
    return re.sub(r"[^a-z0-9]", "", value.casefold()) in re.sub(r"[^a-z0-9]", "", text.casefold())


def _named_vehicles(vehicles: list[VehicleRecord], text: str) -> list[VehicleRecord]:
    words = set(re.findall(r"[a-z0-9]+", text.casefold()))
    matches = []
    for vehicle in vehicles:
        model_words = set(re.findall(r"[a-z0-9]+", vehicle.model.casefold())) - {"cng", "diesel"}
        if _mentioned(vehicle.make, text) or model_words & words:
            matches.append(vehicle)
    return matches


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
    mode: Annotated[SearchMode, Field(description="new search, refinement, or more results")],
    budget_min: Annotated[int, Field(ge=0, description="Minimum INR budget stated by the user")] | None = None,
    budget_max: Annotated[
        int,
        Field(ge=0, description="Maximum INR budget stated by the user; convert 20 lakh to 2000000"),
    ]
    | None = None,
    body_type: Annotated[
        BodyType,
        Field(description="Physical cargo body; pickup is a vehicle category, not a body type; do not infer it"),
    ]
    | None = None,
    fuel: Annotated[FuelType, Field(description="Fuel stated by the user; do not infer it")] | None = None,
    city: Annotated[str, Field(description="Listing city; for a route use its origin city")] | None = None,
    purpose: Annotated[PurposeTag, Field(description="Closest intended work or route type; ranking signal only")]
    | None = None,
    category: Annotated[
        VehicleCategory,
        Field(description="Vehicle category stated by the user: mini_truck, pickup, or rigid_truck"),
    ]
    | None = None,
    size: Annotated[
        WeightClass,
        Field(
            description=(
                "Exact stated size: light, intermediate, medium, or heavy; "
                "chhota/small means light and bada/heavy means heavy"
            )
        ),
    ]
    | None = None,
    make: Annotated[str, Field(description="Manufacturer name only, for example Tata or Mahindra")] | None = None,
    model: Annotated[
        str,
        Field(description="Full or partial model name without the manufacturer, for example Ace or Ace Gold"),
    ]
    | None = None,
    payload_min_kg: Annotated[int, Field(ge=0, description="Minimum payload only when a number is stated")]
    | None = None,
    gvw_min_kg: Annotated[int, Field(ge=0, description="Minimum GVW only when a number is stated")] | None = None,
    papers_verified: bool | None = None,
    clear_fields: list[SearchField] | None = None,
) -> str:
    """Start, refine, or paginate a search using constraints from this turn.

    Always use this tool when the user adds, removes, corrects, or prefers a
    constraint, even when the same turn asks which option is best. Use mode=new
    for a fresh request, refine for a change to the current search, and more to
    exclude results already shown. Omitted arguments preserve current values in
    refine and more modes. Infer size and purpose; category, body, and fuel must
    be explicit.

    Accepted values and numeric constraints are declared in the tool schema.
    """
    logger.info("tool_called", extra={"tool": "search_vehicles"})
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

    current_filters = SearchFilters() if mode == "new" else context.state.active_filters
    filters, changed_fields = merge_slot_patch(current_filters, patch)
    excluded_ids = context.state.shown_result_ids if mode == "more" else []
    result = await asyncio.to_thread(search_catalog, filters, changed_fields, excluded_ids)

    context.state.active_filters = filters
    context.state.last_result_ids = [item.vehicle.listing_id for item in result.vehicles]
    context.state.last_result_labels = [f"{item.vehicle.make} {item.vehicle.model}" for item in result.vehicles]
    if mode == "more":
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
        return _set_response(context, message_response("Which vehicle details would you like?"))

    if not state.last_result_ids:
        return _set_response(context, message_response("Please search for vehicles first."))

    vehicles: list[VehicleRecord] | None = None
    if scope == "all":
        listing_ids = list(state.last_result_ids)
    elif result_number is not None:
        if result_number > len(state.last_result_ids):
            return _set_response(context, message_response("I don't have that result number in the previous search."))
        listing_ids = [state.last_result_ids[result_number - 1]]
    elif state.selected_listing_id:
        listing_ids = [state.selected_listing_id]
    else:
        candidates, context.catalog_ms = await asyncio.to_thread(get_vehicles, state.last_result_ids)
        vehicles = _named_vehicles(candidates, context.current_input)
        if not vehicles:
            return _set_response(
                context,
                message_response("Which previous result do you mean: first, second, or third?"),
            )
        listing_ids = [vehicle.listing_id for vehicle in vehicles]

    if vehicles is None:
        vehicles, context.catalog_ms = await asyncio.to_thread(get_vehicles, listing_ids)
    if not vehicles:
        return _set_response(
            context,
            message_response("Those previous vehicles are no longer available in the catalog."),
        )

    state.selected_listing_id = listing_ids[0] if len(listing_ids) == 1 else None
    comparison = mode if mode in comparison_fields else None
    return _set_response(context, details_response(vehicles, fields, comparison))


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
    include_purposes: bool = False,
) -> str:
    """List available cities, vehicle categories, body types, fuels, makes, or purposes."""
    logger.info("tool_called", extra={"tool": "list_catalog_options"})
    context = ctx.context
    context.action = AgentAction.catalog_options
    requested = {
        CatalogTopic.cities: include_cities,
        CatalogTopic.vehicle_categories: include_categories,
        CatalogTopic.body_types: include_body_types,
        CatalogTopic.fuels: include_fuels,
        CatalogTopic.makes: include_makes,
        CatalogTopic.purposes: include_purposes,
    }
    topics = [topic for topic, included in requested.items() if included]
    if not topics:
        return _set_response(context, message_response("Which catalog options would you like to know about?"))

    options, context.catalog_ms = await asyncio.to_thread(get_catalog_options, topics)
    return _set_response(context, catalog_options_response(options))
