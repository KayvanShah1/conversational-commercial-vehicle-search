from types import SimpleNamespace

from pydantic import SecretStr
from vehicle_search_agent.agent import FallbackModel, _tool_result, build_agent
from vehicle_search_agent.models import AgentAction, ConversationState
from vehicle_search_agent.response import message_response
from vehicle_search_agent.settings import settings
from vehicle_search_agent.tools import AgentContext, retry_tool_error

from agents import ModelRetryNormalizedError, RetryPolicyContext


def test_fallback_model_restarts_for_a_new_user_turn():
    model = FallbackModel([SimpleNamespace(model="first"), SimpleNamespace(model="second")])
    model.advance()

    model.reset()

    assert model.model == "first"


def test_tool_validation_retries_are_bounded_at_three():
    context = AgentContext(state=ConversationState(session_id="test"))
    wrapper = SimpleNamespace(context=context)

    for _ in range(2):
        retry_tool_error(wrapper, ValueError("bad arguments"))
        assert not _tool_result(wrapper, []).is_final_output

    retry_tool_error(wrapper, ValueError("bad arguments"))

    assert _tool_result(wrapper, []).is_final_output


def test_search_result_stops_without_another_model_call():
    context = AgentContext(state=ConversationState(session_id="test"))
    context.action = AgentAction.search
    context.grounded_response = message_response("Grounded search result.")

    result = _tool_result(SimpleNamespace(context=context), [])

    assert result.is_final_output
    assert result.final_output == "Grounded search result."


def test_comparison_details_return_to_model_for_grounded_reasoning():
    context = AgentContext(state=ConversationState(session_id="test"), current_input="Why is the second one better?")
    context.action = AgentAction.details
    context.grounded_response = message_response("Grounded detail facts.")

    assert not _tool_result(SimpleNamespace(context=context), []).is_final_output


def test_rate_limit_walks_the_configured_model_chain_without_delay():
    agent = build_agent()
    expected_models = [
        "openai/gpt-oss-20b",
        "qwen/qwen3.6-27b",
        "qwen/qwen3.8-27b",
    ]

    for attempt, expected_model in enumerate(expected_models, start=1):
        retry_context = RetryPolicyContext(
            error=RuntimeError("rate limited"),
            attempt=attempt,
            max_retries=3,
            stream=False,
            normalized=ModelRetryNormalizedError(status_code=429),
        )
        decision = agent.model_settings.retry.policy(retry_context)

        assert decision.retry
        assert decision.delay == 0
        assert agent.model.model == expected_model


def test_final_model_uses_short_provider_cooldown():
    agent = build_agent()
    while agent.model.advance() is not None:
        pass
    retry_context = RetryPolicyContext(
        error=RuntimeError("rate limited"),
        attempt=4,
        max_retries=7,
        stream=False,
        normalized=ModelRetryNormalizedError(status_code=429, retry_after=6.5),
    )

    decision = agent.model_settings.retry.policy(retry_context)

    assert decision.retry
    assert decision.delay == 6.5


def test_openrouter_models_are_retained_after_groq_fallbacks(monkeypatch):
    monkeypatch.setattr(settings.openrouter, "api_key", SecretStr("test-key"))

    agent = build_agent()

    assert [str(model.model) for model in agent.model.models][-2:] == [
        "google/gemma-4-26b-a4b-it:free",
        "google/gemma-4-31b-it:free",
    ]
