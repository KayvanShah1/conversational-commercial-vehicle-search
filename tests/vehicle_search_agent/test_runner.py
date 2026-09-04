import asyncio
from types import SimpleNamespace

import pytest
from agents.usage import Usage
from vehicle_search_agent.models import (
    AgentAction,
    AgentTurnResult,
    ConversationState,
    SearchFilters,
    TurnMetrics,
    TurnUsage,
)
from vehicle_search_agent.runner import AgentStageTimer, VehicleSearchSession, _llm_list_cost_usd, _tool_choice
from vehicle_search_agent.tools import AgentContext

from agents import RunContextWrapper


def _run_result(output: str, *, input_tokens: int = 0, output_tokens: int = 0):
    usage = Usage(
        requests=1,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
    )
    return SimpleNamespace(final_output=output, context_wrapper=SimpleNamespace(usage=usage))


def test_state_change_language_routes_any_slot_through_search():
    state = ConversationState(session_id="test")
    state.active_filters.city = "Mumbai"
    state.last_result_ids = ["VEH-001"]

    assert _tool_choice("I prefer diesel", state) == "search_vehicles"
    assert _tool_choice("Actually make it Delhi", state) == "search_vehicles"
    assert _tool_choice("Switch to a box body", state) == "search_vehicles"
    assert _tool_choice("Which one is cheapest?", state) == "auto"
    assert _tool_choice("Give me more details about the first one", state) == "get_vehicle_details"
    assert _tool_choice("I need more detaila about Tata Ace", state) == "get_vehicle_details"


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
        return _run_result(next(responses), input_tokens=100, output_tokens=20)

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
    assert next_result.usage.total_tokens == 120


def test_no_tool_numeric_claim_uses_safe_fallback(monkeypatch):
    async def fake_run(*args, **kwargs):
        return _run_result("That Tata costs INR 4 lakh.")

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


def test_tool_choice_resets_after_failed_turn(monkeypatch):
    async def fake_run(*args, **kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr("vehicle_search_agent.runner.Runner.run", staticmethod(fake_run))

    session = object.__new__(VehicleSearchSession)
    session.session_id = "test-session"
    state = ConversationState(session_id=session.session_id)
    state.active_filters.city = "Mumbai"
    session.context = AgentContext(state=state)
    session.agent = SimpleNamespace(
        model=SimpleNamespace(model="test-model"), model_settings=SimpleNamespace(tool_choice="auto")
    )
    session.sdk_session = object()
    session.hooks = AgentStageTimer()

    with pytest.raises(RuntimeError, match="provider unavailable"):
        asyncio.run(session.run_text_turn("Actually make it Delhi"))

    assert session.agent.model_settings.tool_choice == "auto"


def test_llm_list_cost_uses_input_and_output_rates():
    assert _llm_list_cost_usd("openai/gpt-oss-120b", 1_000_000, 1_000_000) == 0.75
    assert _llm_list_cost_usd("unknown-model", 100, 100) is None


def test_stage_hook_accumulates_priced_model_usage():
    context = AgentContext(state=ConversationState(session_id="test"))
    agent = SimpleNamespace(model=SimpleNamespace(model="openai/gpt-oss-120b"))
    response = SimpleNamespace(
        usage=Usage(requests=1, input_tokens=1_000_000, output_tokens=1_000_000, total_tokens=2_000_000)
    )

    asyncio.run(AgentStageTimer().on_llm_end(RunContextWrapper(context), agent, response))

    assert context.llm_list_cost_usd == 0.75
    assert context.pricing_complete


def test_voice_turn_measures_server_receipt_to_audio_ready(monkeypatch):
    monkeypatch.setattr(
        "vehicle_search_agent.runner.transcribe_audio",
        lambda *args, **kwargs: SimpleNamespace(text="Hi", duration_ms=100.0, audio_seconds=2.0),
    )
    monkeypatch.setattr(
        "vehicle_search_agent.runner.synthesize_speech",
        lambda text: SimpleNamespace(audio=b"wav", duration_ms=200.0, format="wav", character_count=20),
    )
    monkeypatch.setattr("vehicle_search_agent.runner.perf_counter", lambda: 10.5)

    async def fake_text_turn(transcript: str) -> AgentTurnResult:
        return AgentTurnResult(
            session_id="test-session",
            turn_number=1,
            transcript=transcript,
            action=AgentAction.conversation,
            spoken_response="Hi, I'm Vivi.",
            active_filters=SearchFilters(),
            last_result_ids=[],
            changed_fields=[],
            model_used="openai/gpt-oss-120b",
            metrics=TurnMetrics(total_ms=300.0),
            usage=TurnUsage(estimated_list_cost_usd=0.001, estimated_list_cost_inr=0.09543),
        )

    session = object.__new__(VehicleSearchSession)
    session.session_id = "test-session"
    session.run_text_turn = fake_text_turn

    result = asyncio.run(session.run_voice_turn(b"audio", speech_ended_at=10.0))

    assert result.metrics.speech_end_to_audio_ready_ms == 500.0
    assert result.metrics.stt_ms == 100.0
    assert result.metrics.tts_ms == 200.0
    assert result.usage.audio_input_seconds == 2.0
    assert result.usage.tts_characters == 20
