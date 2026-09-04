from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass, field
from typing import Annotated, Any, Literal

from openai import AsyncOpenAI
from pydantic import Field
from rich.console import Console
from rich.table import Table
from vehicle_search_agent.settings import settings

from agents import Agent, ModelSettings, OpenAIChatCompletionsModel, RunContextWrapper, Runner, function_tool

PROMPT = """
Choose one tool from meaning. A request for matching vehicles uses
search_vehicles; list_catalog_options is only for asking which catalog facet
values exist. Any search constraint requires search_vehicles, including a
standalone statement or one combined with a comparison. Use get_vehicle_details
for prior-result questions without a changed constraint. "More details" means
all_details. An existing search with a changed constraint is refine, not new.
Put operation and reference meaning in mode and scope. General guidance uses no tool.
"""
PREVIOUS_RESULTS = "Results: 1. Tata Ace Gold, 2. Mahindra Jeeto, 3. Ashok Leyland Bada Dost. Budget: INR 8 lakh."


@dataclass(frozen=True)
class Case:
    name: str
    text: str
    tool: str
    arguments: dict[str, Any]
    with_results: bool = False


CASES = (
    Case("new_search", "My bidget is 20 lakhs.", "search_vehicles", {"mode": "new", "budget_max": 2_000_000}),
    Case(
        "one_result",
        "Tell me more about the second one.",
        "get_vehicle_details",
        {"scope": "one", "mode": "all_details", "result_number": 2},
        True,
    ),
    Case(
        "compare_all", "Which among these is best?", "get_vehicle_details", {"scope": "all", "mode": "best_match"}, True
    ),
    Case(
        "refine",
        "Which is best? I prefer diesel.",
        "search_vehicles",
        {"mode": "refine", "fuel": "Diesel"},
        True,
    ),
    Case("more", "Suggest a few more.", "search_vehicles", {"mode": "more"}, True),
    Case("cities", "Which locations have listings?", "list_catalog_options", {"topic": "cities"}),
)


@dataclass
class Context:
    tool: str | None = None
    arguments: dict[str, Any] = field(default_factory=dict)


def _record(ctx: RunContextWrapper[Context], tool: str, **arguments: Any) -> str:
    ctx.context.tool, ctx.context.arguments = tool, arguments
    return "Intent recorded."


@function_tool(strict_mode=False)
async def search_vehicles(
    ctx: RunContextWrapper[Context],
    mode: Literal["new", "refine", "more"],
    budget_max: Annotated[int, Field(ge=0, description="maximum INR; 20 lakh is 2000000")] | None = None,
    fuel: Literal["CNG", "Diesel"] | None = None,
) -> str:
    """Find matching vehicles, refine their constraints, or get more results."""
    return _record(ctx, "search_vehicles", mode=mode, budget_max=budget_max, fuel=fuel)


@function_tool(strict_mode=False)
async def get_vehicle_details(
    ctx: RunContextWrapper[Context],
    scope: Literal["one", "all"],
    mode: Literal["facts", "all_details", "best_match"],
    result_number: Annotated[int, Field(ge=1, le=3)] | None = None,
) -> str:
    """Read facts for one prior result or compare all current results."""
    return _record(ctx, "get_vehicle_details", scope=scope, mode=mode, result_number=result_number)


@function_tool(strict_mode=False)
async def list_catalog_options(
    ctx: RunContextWrapper[Context], topic: Literal["cities", "vehicle_types", "fuels", "body_types", "makes"]
) -> str:
    """List which values exist for one catalog facet; do not find vehicles."""
    return _record(ctx, "list_catalog_options", topic=topic)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke-test semantic tool routing without catalog access.")
    parser.add_argument("--model", action="append", dest="models")
    parser.add_argument("--delay-seconds", type=float, default=2.0)
    return parser.parse_args()


async def _run(models: list[str], delay: float) -> bool:
    console, all_passed = Console(), True
    client = AsyncOpenAI(api_key=settings.groq.api_keys[0].get_secret_value(), base_url=settings.groq.base_url)
    try:
        for model_name in models:
            model = OpenAIChatCompletionsModel(model=model_name, openai_client=client)
            agent = Agent[Context](
                name="Intent routing smoke",
                instructions=PROMPT,
                model=model,
                model_settings=ModelSettings(
                    temperature=0.0,
                    tool_choice="auto",
                    parallel_tool_calls=False,
                    timeout=settings.agent_runtime.model_timeout_seconds,
                ),
                tools=[search_vehicles, get_vehicle_details, list_catalog_options],
                tool_use_behavior="stop_on_first_tool",
            )
            table = Table(title=model_name)
            for heading in ("Case", "Expected", "Actual", "Result"):
                table.add_column(heading)
            for index, case in enumerate(CASES):
                if index and delay:
                    await asyncio.sleep(delay)
                context = Context()
                inputs = case.text
                if case.with_results:
                    inputs = [
                        {"role": "assistant", "content": PREVIOUS_RESULTS},
                        {"role": "user", "content": case.text},
                    ]
                try:
                    await Runner.run(agent, inputs, context=context, max_turns=2)
                    passed = context.tool == case.tool and all(
                        context.arguments.get(name) == value for name, value in case.arguments.items()
                    )
                    actual = f"{context.tool} {json.dumps(context.arguments, sort_keys=True)}"
                except Exception as error:  # noqa: BLE001 - report every case in one run
                    passed, actual = False, f"{type(error).__name__}: {error}"
                all_passed &= passed
                table.add_row(case.name, f"{case.tool} {case.arguments}", actual, "PASS" if passed else "FAIL")
            console.print(table)
    finally:
        await client.close()
    return all_passed


def main() -> None:
    arguments = _arguments()
    models = arguments.models or [settings.groq.primary_model, *settings.groq.fallback_models]
    if not asyncio.run(_run(list(dict.fromkeys(models)), arguments.delay_seconds)):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
