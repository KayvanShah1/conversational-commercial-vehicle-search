import asyncio
import json

import vehicle_search_agent.tools as tools_module
from agents.tool_context import ToolContext
from vehicle_search_agent.models import ConversationState, VehicleRecord, VehicleSearchResult
from vehicle_search_agent.tools import AgentContext, get_vehicle_details, search_vehicles


def _vehicle(listing_id: str) -> VehicleRecord:
    return VehicleRecord(
        listing_id=listing_id,
        make="Tata",
        model=listing_id,
        year=2022,
        price_inr=1_000_000,
        km_driven=20_000,
        fuel="Diesel",
        payload_kg=2_000,
        gvw_kg=4_000,
        vehicle_category="pickup",
        weight_class="light",
        body_type="open",
        axle_count=2,
        city="Pune",
        papers_verified=True,
        condition="good",
        purpose_tags=["city_delivery"],
        spec_source_url="https://example.com",
    )


def _context(user_input: str) -> AgentContext:
    state = ConversationState(
        session_id="test",
        last_result_ids=["VEH-001", "VEH-002", "VEH-003"],
        selected_listing_id="VEH-001",
    )
    return AgentContext(state=state, current_input=user_input)


def _invoke(context: AgentContext, arguments: dict) -> None:
    encoded = json.dumps(arguments)
    tool_context = ToolContext(
        context=context,
        tool_name="get_vehicle_details",
        tool_call_id="test-call",
        tool_arguments=encoded,
    )
    asyncio.run(get_vehicle_details.on_invoke_tool(tool_context, encoded))


def test_search_keeps_explicit_enum_words_when_model_omits_them(monkeypatch):
    context = AgentContext(
        state=ConversationState(session_id="test"),
        current_input="Show me a heavy diesel rigid truck with a tipper body.",
    )

    def fake_search(filters, changed_fields, excluded_ids):
        assert filters.fuel == "Diesel"
        assert filters.body_type == "tipper"
        assert filters.vehicle_category == "rigid_truck"
        assert not excluded_ids
        return VehicleSearchResult(
            executed_filters=filters,
            changed_fields=changed_fields,
            vehicles=[],
            total_matches=0,
            search_ms=1,
        )

    monkeypatch.setattr(tools_module, "search_catalog", fake_search)
    encoded = json.dumps({"size": "heavy"})
    tool_context = ToolContext(
        context=context,
        tool_name="search_vehicles",
        tool_call_id="test-call",
        tool_arguments=encoded,
    )

    asyncio.run(search_vehicles.on_invoke_tool(tool_context, encoded))


def test_plural_reference_overrides_a_previous_single_selection(monkeypatch):
    context = _context("What can they carry and how much weight?")

    def fake_lookup(listing_ids):
        return [_vehicle(listing_id) for listing_id in listing_ids], 1.0

    monkeypatch.setattr(tools_module, "get_vehicles", fake_lookup)
    _invoke(context, {"fields": ["payload", "gvw"], "result_number": 1})

    assert len(context.grounded_response.facts) == 3


def test_all_details_for_an_ordinal_returns_every_user_facing_field(monkeypatch):
    context = _context("Give me all details for the first one.")

    def fake_lookup(listing_ids):
        return [_vehicle(listing_id) for listing_id in listing_ids], 1.0

    monkeypatch.setattr(tools_module, "get_vehicles", fake_lookup)
    _invoke(context, {"result_number": 1, "all_details": True})

    assert len(context.grounded_response.facts) == 1
    fact = context.grounded_response.facts[0].casefold()
    for label in (
        "year",
        "price",
        "km",
        "payload",
        "gvw",
        "body type",
        "papers",
        "category",
        "size class",
        "axles",
        "specification source",
    ):
        assert label in fact


def test_brochure_question_returns_sources_for_all_results(monkeypatch):
    context = _context("Do these have any brochures?")

    def fake_lookup(listing_ids):
        return [_vehicle(listing_id) for listing_id in listing_ids], 1.0

    monkeypatch.setattr(tools_module, "get_vehicles", fake_lookup)
    _invoke(context, {"fields": ["spec_source_url"]})

    assert len(context.grounded_response.facts) == 3
    assert all("specification source https://example.com" in fact for fact in context.grounded_response.facts)
