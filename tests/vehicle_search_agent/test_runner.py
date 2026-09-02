import asyncio
from types import SimpleNamespace

from vehicle_search_agent.models import ConversationState
from vehicle_search_agent.runner import AgentStageTimer, VehicleSearchSession, _tool_choice
from vehicle_search_agent.tools import AgentContext


def test_state_change_language_routes_any_slot_through_search():
    state = ConversationState(session_id="test")
    state.active_filters.city = "Mumbai"

    assert _tool_choice("I prefer diesel", state) == "search_vehicles"
    assert _tool_choice("Actually make it Delhi", state) == "search_vehicles"
    assert _tool_choice("Switch to a box body", state) == "search_vehicles"
    assert _tool_choice("Which one is cheapest?", state) == "auto"


def test_state_change_rule_does_not_override_first_turn_intent_detection():
    state = ConversationState(session_id="test")

    assert _tool_choice("I prefer diesel", state) == "auto"


def test_agent_can_answer_side_questions_without_a_tool(monkeypatch):
    responses = iter(
        (
            "Hi! I'm Vivi, and I can help you find a used commercial vehicle.",
            "I can search by budget, fuel, city, body type, or intended use.",
        )
    )

    async def fake_run(*args, **kwargs):
        return SimpleNamespace(final_output=next(responses))

    monkeypatch.setattr("vehicle_search_agent.runner.Runner.run", staticmethod(fake_run))

    session = object.__new__(VehicleSearchSession)
    session.session_id = "test-session"
    session.context = AgentContext(state=ConversationState(session_id=session.session_id))
    session.agent = SimpleNamespace(
        model=SimpleNamespace(model="test-model"), model_settings=SimpleNamespace(tool_choice="auto")
    )
    session.sdk_session = object()
    session.hooks = AgentStageTimer()

    result = asyncio.run(session.run_text_turn("Hi"))

    assert result.spoken_response == (
        "Hey, I'm Vivi. Tell me what you need to transport, your budget, and where you're looking."
    )

    next_result = asyncio.run(session.run_text_turn("What can you help me with?"))

    assert next_result.spoken_response == "I can search by budget, fuel, city, body type, or intended use."


def test_no_tool_numeric_claim_uses_safe_fallback(monkeypatch):
    async def fake_run(*args, **kwargs):
        return SimpleNamespace(final_output="That Tata costs INR 4 lakh.")

    monkeypatch.setattr("vehicle_search_agent.runner.Runner.run", staticmethod(fake_run))

    session = object.__new__(VehicleSearchSession)
    session.session_id = "test-session"
    session.context = AgentContext(state=ConversationState(session_id=session.session_id))
    session.agent = SimpleNamespace(
        model=SimpleNamespace(model="test-model"), model_settings=SimpleNamespace(tool_choice="auto")
    )
    session.sdk_session = object()
    session.hooks = AgentStageTimer()

    result = asyncio.run(session.run_text_turn("Tell me its price"))

    assert "INR 4 lakh" not in result.spoken_response
    assert result.spoken_response.startswith("Hi, I'm Vivi.")
