import asyncio
import re
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field
from pydantic.fields import FieldInfo

from agents import RunContextWrapper, function_tool
from vehicle_search_agent.models import (
    AgentAction,
    BodyType,
    FuelType,
    PurposeTag,
    SearchField,
    SearchFilters,
    SlotPatch,
    VehicleCategory,
    WeightClass,
    merge_slot_patch,
)
from vehicle_search_agent.response import search_response
from vehicle_search_agent.search import search_catalog
from vehicle_search_agent.settings import settings
from vehicle_search_agent.tools.context import AgentContext, logger, retry_tool_error, set_response

SearchMode = Literal["new", "refine", "more"]


def _enum_argument(enum_type: type[StrEnum], description: str) -> FieldInfo:
    values = [item.value for item in enum_type]
    pattern = "^(?:" + "|".join(re.escape(value) for value in values) + ")$"
    return Field(description=description, pattern=pattern, json_schema_extra={"enum": values})


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
        str,
        _enum_argument(
            BodyType,
            "Physical cargo body; pickup is a vehicle category, not a body type; do not infer it",
        ),
    ]
    | None = None,
    fuel: Annotated[str, _enum_argument(FuelType, "Fuel stated by the user; do not infer it")] | None = None,
    city: Annotated[str, Field(description="Listing city; for a route use its origin city")] | None = None,
    purpose: Annotated[
        str,
        _enum_argument(
            PurposeTag,
            (
                "Closest intended work or route type; ranking signal only. Use heavy_delivery for transporting "
                "heavy machinery and industrial_goods for general industrial cargo"
            ),
        ),
    ]
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
                "Map explicit size words exactly: light to light, intermediate to intermediate, "
                "medium to medium, and heavy to heavy; map chhota/small to light and bada to heavy"
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
    return set_response(context, search_response(result))
