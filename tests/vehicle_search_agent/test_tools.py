import asyncio
import json

import vehicle_search_agent.tools.context as tool_context_module
import vehicle_search_agent.tools.details as details_tool_module
import vehicle_search_agent.tools.search as search_tool_module
from agents.tool_context import ToolContext
from vehicle_search_agent.models import ConversationState, VehicleRecord, VehicleSearchResult
from vehicle_search_agent.response import GroundedResponse
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


def test_rephrase_instruction_keeps_km_driven_distinct_from_fuel_mileage():
    response = GroundedResponse(
        fallback="Tata Test has covered 20,000 km.",
        facts=("20,000 km",),
        checks=(("20,000",),),
    )

    request = tool_context_module.rephrase_request(response, first_turn=False)

    assert "Never describe kilometres driven or an odometer reading as mileage or fuel economy." in request


def test_search_uses_the_models_typed_slot_extraction(monkeypatch):
    logs = []
    context = AgentContext(
        state=ConversationState(session_id="test"),
        current_input="Show me a heavy diesel rigid truck with a tipper body.",
        model_name="openai/gpt-oss-120b",
        model_route="groq-key-2/openai/gpt-oss-120b",
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

    monkeypatch.setattr(search_tool_module, "search_catalog", fake_search)
    monkeypatch.setattr(tool_context_module.logger, "info", lambda message, *, extra: logs.append((message, extra)))
    encoded = json.dumps(
        {
            "mode": "new",
            "size": "heavy",
            "fuel": "Diesel",
            "body_type": "tipper",
            "category": "rigid_truck",
        }
    )
    tool_context = ToolContext(
        context=context,
        tool_name="search_vehicles",
        tool_call_id="test-call",
        tool_arguments=encoded,
    )

    asyncio.run(search_vehicles.on_invoke_tool(tool_context, encoded))

    assert logs == [
        (
            "tool_called",
            {
                "tool": "search_vehicles",
                "model": "openai/gpt-oss-120b",
                "model_route": "groq-key-2/openai/gpt-oss-120b",
            },
        )
    ]


def test_zero_result_search_preserves_the_last_successful_result_references(monkeypatch):
    context = AgentContext(
        state=ConversationState(
            session_id="test",
            last_result_ids=["VEH-001", "VEH-002", "VEH-003"],
            last_result_labels=["Tata One", "Tata Two", "Tata Three"],
            shown_result_ids=["VEH-001", "VEH-002", "VEH-003"],
            selected_listing_id="VEH-002",
        ),
        current_input="Only CNG tankers under 1 lakh in Kolkata.",
    )

    def fake_search(filters, changed_fields, excluded_ids):
        assert filters.city == "Kolkata"
        assert not excluded_ids
        return VehicleSearchResult(
            executed_filters=filters,
            changed_fields=changed_fields,
            vehicles=[],
            total_matches=0,
            relaxation="budget",
            search_ms=1,
        )

    monkeypatch.setattr(search_tool_module, "search_catalog", fake_search)
    encoded = json.dumps({"mode": "new", "city": "Kolkata"})
    tool_context = ToolContext(
        context=context,
        tool_name="search_vehicles",
        tool_call_id="test-call",
        tool_arguments=encoded,
    )

    asyncio.run(search_vehicles.on_invoke_tool(tool_context, encoded))

    assert context.state.last_result_ids == ["VEH-001", "VEH-002", "VEH-003"]
    assert context.state.last_result_labels == ["Tata One", "Tata Two", "Tata Three"]
    assert context.state.shown_result_ids == ["VEH-001", "VEH-002", "VEH-003"]
    assert context.state.selected_listing_id == "VEH-002"
    assert context.last_search_result is not None
    assert not context.last_search_result.vehicles


def test_more_mode_excludes_previously_shown_results(monkeypatch):
    context = AgentContext(
        state=ConversationState(
            session_id="test",
            active_filters={"fuel": "Diesel"},
            shown_result_ids=["VEH-001", "VEH-002"],
        )
    )

    def fake_search(filters, changed_fields, excluded_ids):
        assert filters.fuel == "Diesel"
        assert excluded_ids == ["VEH-001", "VEH-002"]
        return VehicleSearchResult(
            executed_filters=filters,
            changed_fields=changed_fields,
            vehicles=[],
            total_matches=0,
            search_ms=1,
        )

    monkeypatch.setattr(search_tool_module, "search_catalog", fake_search)
    encoded = json.dumps({"mode": "more"})
    tool_context = ToolContext(
        context=context,
        tool_name="search_vehicles",
        tool_call_id="test-call",
        tool_arguments=encoded,
    )

    asyncio.run(search_vehicles.on_invoke_tool(tool_context, encoded))


def test_all_scope_overrides_a_previous_single_selection(monkeypatch):
    context = _context("What can they carry and how much weight?")

    def fake_lookup(listing_ids):
        return [_vehicle(listing_id) for listing_id in listing_ids], 1.0

    monkeypatch.setattr(details_tool_module, "get_vehicles", fake_lookup)
    _invoke(context, {"scope": "all", "mode": "capability"})

    assert len(context.grounded_response.facts) == 3
    assert all("payload" in fact and "GVW" in fact and "body type" in fact for fact in context.grounded_response.facts)


def test_all_details_for_an_ordinal_returns_every_user_facing_field(monkeypatch):
    context = _context("Give me all details for the first one.")

    def fake_lookup(listing_ids):
        return [_vehicle(listing_id) for listing_id in listing_ids], 1.0

    monkeypatch.setattr(details_tool_module, "get_vehicles", fake_lookup)
    _invoke(context, {"scope": "one", "mode": "all_details", "result_number": 1})

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


def test_requested_fields_for_an_ordinal_return_only_those_fields(monkeypatch):
    context = _context("Second one ka payload aur GVW kya hai?")

    def fake_lookup(listing_ids):
        assert listing_ids == ["VEH-002"]
        return [_vehicle("VEH-002")], 1.0

    monkeypatch.setattr(details_tool_module, "get_vehicles", fake_lookup)
    _invoke(
        context,
        {
            "scope": "one",
            "mode": "facts",
            "fields": ["payload", "gvw"],
            "result_number": 2,
        },
    )

    assert context.grounded_response.facts == ("Tata VEH-002: payload 2,000 kg, GVW 4,000 kg",)
    assert "Payload" in context.grounded_response.display_markdown
    assert "GVW" in context.grounded_response.display_markdown
    assert "Body" not in context.grounded_response.display_markdown
    assert "Listed uses" not in context.grounded_response.display_markdown


def test_intuitive_category_and_axles_aliases_are_accepted(monkeypatch):
    context = _context(
        "What are the kilometers driven and the category of the first one and how many axles does it have?"
    )

    def fake_lookup(listing_ids):
        assert listing_ids == ["VEH-001"]
        return [_vehicle("VEH-001")], 1.0

    monkeypatch.setattr(details_tool_module, "get_vehicles", fake_lookup)
    _invoke(
        context,
        {
            "scope": "one",
            "mode": "facts",
            "fields": ["km_driven", "category", "axles"],
            "result_number": 1,
        },
    )

    assert context.grounded_response.facts == ("Tata VEH-001: 20,000 km, category pickup, axles 2",)
    assert "Kilometres driven" in context.grounded_response.display_markdown
    assert "Category" in context.grounded_response.display_markdown
    assert "Axles" in context.grounded_response.display_markdown


def test_named_details_are_limited_to_matching_previous_results(monkeypatch):
    context = _context("Give me more details about the Mahindra Jeeto.")
    context.state.selected_listing_id = None
    catalog = {
        "VEH-001": _vehicle("VEH-001").model_copy(update={"make": "Mahindra", "model": "Jeeto Strong Diesel"}),
        "VEH-002": _vehicle("VEH-002").model_copy(update={"make": "Tata", "model": "Ace Gold"}),
        "VEH-003": _vehicle("VEH-003").model_copy(update={"make": "Mahindra", "model": "Jeeto Strong Diesel"}),
    }

    def fake_lookup(listing_ids):
        return [catalog[listing_id] for listing_id in listing_ids], 1.0

    monkeypatch.setattr(details_tool_module, "get_vehicles", fake_lookup)
    _invoke(context, {"scope": "one", "mode": "all_details"})

    assert len(context.grounded_response.facts) == 2
    assert all(fact.startswith("Mahindra Jeeto Strong Diesel") for fact in context.grounded_response.facts)
    assert context.state.selected_listing_id is None


def test_brochure_question_returns_sources_for_all_results(monkeypatch):
    context = _context("Do these have any brochures?")

    def fake_lookup(listing_ids):
        return [_vehicle(listing_id) for listing_id in listing_ids], 1.0

    monkeypatch.setattr(details_tool_module, "get_vehicles", fake_lookup)
    _invoke(context, {"scope": "all", "mode": "facts", "fields": ["spec_source_url"]})

    assert len(context.grounded_response.facts) == 3
    assert all("specification source https://example.com" in fact for fact in context.grounded_response.facts)
