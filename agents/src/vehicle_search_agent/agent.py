from __future__ import annotations

import re
from typing import Any

from openai import AsyncOpenAI
from vehicle_search_utils import get_logger

from agents import (
    Agent,
    FunctionToolResult,
    Model,
    ModelRetrySettings,
    ModelSettings,
    OpenAIChatCompletionsModel,
    RetryDecision,
    RunContextWrapper,
    ToolsToFinalOutputResult,
)
from vehicle_search_agent.models import AgentAction
from vehicle_search_agent.prompts import SYSTEM_PROMPT
from vehicle_search_agent.settings import settings
from vehicle_search_agent.tools import AgentContext, get_vehicle_details, list_catalog_options, search_vehicles

logger = get_logger("VehicleSearchAgent")


class FallbackModel(Model):
    """Use the next configured model after a retryable provider failure."""

    def __init__(self, models: list[OpenAIChatCompletionsModel]) -> None:
        self.models = models
        self.index = 0

    @property
    def model(self) -> str:
        return str(self.models[self.index].model)

    def advance(self) -> str | None:
        if self.index == len(self.models) - 1:
            return None
        self.index += 1
        return self.model

    def reset(self) -> None:
        self.index = 0

    def get_retry_advice(self, request: Any) -> Any:
        return self.models[self.index].get_retry_advice(request)

    async def get_response(self, *args: Any, **kwargs: Any) -> Any:
        return await self.models[self.index].get_response(*args, **kwargs)

    def stream_response(self, *args: Any, **kwargs: Any) -> Any:
        return self.models[self.index].stream_response(*args, **kwargs)

    async def close(self) -> None:
        for model in self.models:
            await model.close()


def _tool_result(
    ctx: RunContextWrapper[AgentContext], _results: list[FunctionToolResult]
) -> ToolsToFinalOutputResult:
    context = ctx.context
    if context.tool_failures >= 3:
        return ToolsToFinalOutputResult(
            is_final_output=True,
            final_output="I couldn't map that request to the catalog fields. Please rephrase the vehicle requirement.",
        )
    grounded = context.grounded_response
    needs_reasoning = context.action is AgentAction.details and re.search(
        r"\b(?:why|better|best|compare|suitable|recommend)\b",
        context.current_input,
        re.IGNORECASE,
    )
    if grounded is not None and not needs_reasoning:
        return ToolsToFinalOutputResult(is_final_output=True, final_output=grounded.fallback)
    return ToolsToFinalOutputResult(is_final_output=False)


def _instructions(ctx: RunContextWrapper[AgentContext], _agent: Agent[AgentContext]) -> str:
    active = ctx.context.state.active_filters.model_dump_json(exclude_none=True)
    turn = ctx.context.state.turn_number
    return f"{SYSTEM_PROMPT}\n\nCurrent turn: {turn}\nCurrent filters: {active}"


def build_agent() -> Agent[AgentContext]:
    api_key = settings.groq.api_key.get_secret_value()
    groq_client = AsyncOpenAI(api_key=api_key, base_url=settings.groq.base_url)
    models = [
        OpenAIChatCompletionsModel(model=model_name, openai_client=groq_client)
        for model_name in [settings.groq.primary_model, *settings.groq.fallback_models]
    ]
    if settings.openrouter.api_key:
        openrouter_key = settings.openrouter.api_key.get_secret_value()
        openrouter_client = AsyncOpenAI(api_key=openrouter_key, base_url=settings.openrouter.base_url)
        models.extend(
            OpenAIChatCompletionsModel(model=model_name, openai_client=openrouter_client)
            for model_name in settings.openrouter.fallback_models
        )
    model = FallbackModel(models)

    def use_next_model(context) -> bool | RetryDecision:
        retryable = (
            context.normalized.status_code in {400, 408, 409, 429, 500, 502, 503, 504}
            or context.normalized.is_network_error
            or context.normalized.is_timeout
        )
        if not retryable:
            return False
        previous_model = model.model
        next_model = model.advance()
        if next_model is None:
            retry_after = context.normalized.retry_after
            return RetryDecision(
                retry=retry_after is None or retry_after <= 30,
                delay=retry_after,
                reason="final model cooldown",
            )
        logger.warning(
            "model_fallback_activated",
            extra={"previous_model": previous_model, "next_model": next_model},
        )
        return RetryDecision(retry=True, delay=0, reason="model fallback")

    model_settings = ModelSettings(
        temperature=0.0,
        tool_choice="auto",
        parallel_tool_calls=False,
        timeout=settings.agent_runtime.model_timeout_seconds,
        retry=ModelRetrySettings(
            max_retries=settings.agent_runtime.model_max_retries,
            policy=use_next_model,
        ),
    )
    return Agent[AgentContext](
        name="Vivi",
        instructions=_instructions,
        model=model,
        model_settings=model_settings,
        tools=[search_vehicles, get_vehicle_details, list_catalog_options],
        tool_use_behavior=_tool_result,
    )
