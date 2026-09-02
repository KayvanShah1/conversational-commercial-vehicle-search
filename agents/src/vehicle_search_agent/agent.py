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

    def __init__(self, models: list[OpenAIChatCompletionsModel], routes: list[str]) -> None:
        if len(models) != len(routes):
            raise ValueError("Each model requires a route label.")
        self.models = models
        self.routes = routes
        self.index = 0

    @property
    def model(self) -> str:
        return str(self.models[self.index].model)

    @property
    def route(self) -> str:
        return self.routes[self.index]

    def advance(self) -> str | None:
        if self.index == len(self.models) - 1:
            return None
        self.index += 1
        return self.route

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
    models: list[OpenAIChatCompletionsModel] = []
    routes: list[str] = []
    groq_clients = [
        AsyncOpenAI(api_key=key.get_secret_value(), base_url=settings.groq.base_url)
        for key in settings.groq.api_keys
    ]
    for model_name in [settings.groq.primary_model, *settings.groq.fallback_models]:
        for key_number, client in enumerate(groq_clients, start=1):
            models.append(OpenAIChatCompletionsModel(model=model_name, openai_client=client))
            routes.append(f"groq-key-{key_number}/{model_name}")

    if settings.openrouter.api_key:
        openrouter_key = settings.openrouter.api_key.get_secret_value()
        openrouter_client = AsyncOpenAI(api_key=openrouter_key, base_url=settings.openrouter.base_url)
        for model_name in settings.openrouter.fallback_models:
            models.append(OpenAIChatCompletionsModel(model=model_name, openai_client=openrouter_client))
            routes.append(f"openrouter/{model_name}")
    model = FallbackModel(models, routes)

    def use_next_model(context) -> bool | RetryDecision:
        retryable = (
            (context.normalized.status_code == 400 and "tool_use_failed" in str(context.error))
            or context.normalized.status_code in {408, 409, 429, 500, 502, 503, 504}
            or context.normalized.is_network_error
            or context.normalized.is_timeout
        )
        if not retryable:
            return False
        previous_route = model.route
        next_route = model.advance()
        if next_route is None:
            return False
        logger.warning(
            "model_fallback_activated",
            extra={"previous_route": previous_route, "next_route": next_route},
        )
        return RetryDecision(retry=True, delay=0, reason="model fallback")

    model_settings = ModelSettings(
        temperature=0.0,
        tool_choice="auto",
        parallel_tool_calls=False,
        timeout=settings.agent_runtime.model_timeout_seconds,
        retry=ModelRetrySettings(
            max_retries=len(models) - 1,
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
