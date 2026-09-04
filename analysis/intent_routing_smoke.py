from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass, field
from time import perf_counter
from typing import Annotated, Any, Literal

from openai import AsyncOpenAI
from pydantic import Field
from rich.console import Console
from rich.table import Table
from vehicle_search_agent.settings import settings

from agents import Agent, ModelSettings, OpenAIChatCompletionsModel, RunContextWrapper, Runner, function_tool

SYSTEM_PROMPT = """
You identify the intent of a commercial-vehicle conversation by choosing the
single matching tool. Interpret the user's meaning instead of matching words.

- search_vehicles: start a search, refine a preference, or request more results.
- get_vehicle_details: inspect one previous result or compare all current results.
- list_catalog_options: ask which listing cities, vehicle types, fuels, bodies, or makes exist.

Use the tool arguments to state the mode and scope. Do not call a tool for
general buying guidance or unrelated requests.
"""

PREVIOUS_RESULTS = (
    "Current results are: 1. Tata Ace Gold, 2. Mahindra Jeeto Strong Diesel, "
    "3. Ashok Leyland Bada Dost i4. The active budget is INR 8 lakh."
)


@dataclass(frozen=True)
class SmokeCase:
    name: str
    utterance: str
    expected_tool: str
    expected_arguments: dict[str, Any]
    has_previous_results: bool = False


@dataclass
class ProbeContext:
    tool: str | None = None
    arguments: dict[str, Any] = field(default_factory=dict)


CASES = (
    SmokeCase(
        "new_search",
        "I need a small truck for city deliveries under 8 lakh.",
        "search_vehicles",
        {"mode": "new", "budget_max": 800_000},
    ),
    SmokeCase(
        "one_result",
        "Tell me more about the second one.",
        "get_vehicle_details",
        {"scope": "one", "result_number": 2},
        True,
    ),
    SmokeCase(
        "compare_all",
        "Which among is the best one?",
        "get_vehicle_details",
        {"scope": "all", "mode": "compare"},
        True,
    ),
    SmokeCase(
        "preference_update",
        "Actually, I prefer diesel.",
        "search_vehicles",
        {"mode": "refine", "fuel": "Diesel"},
        True,
    ),
    SmokeCase(
        "more_results",
        "Can you suggest a few more?",
        "search_vehicles",
        {"mode": "more"},
        True,
    ),
    SmokeCase(
        "catalog_cities",
        "Which locations do you currently have listings in?",
        "list_catalog_options",
        {"topic": "cities"},
    ),
)


def _record(ctx: RunContextWrapper[ProbeContext], tool: str, arguments: dict[str, Any]) -> str:
    ctx.context.tool = tool
    ctx.context.arguments = arguments
    return "Intent recorded."


@function_tool(strict_mode=False)
async def search_vehicles(
    ctx: RunContextWrapper[ProbeContext],
    mode: Literal["new", "refine", "more"],
    budget_max: Annotated[int, Field(ge=0)] | None = None,
    fuel: Literal["CNG", "Diesel"] | None = None,
) -> str:
    """Start a vehicle search, refine its constraints, or request more results."""
    return _record(ctx, "search_vehicles", {"mode": mode, "budget_max": budget_max, "fuel": fuel})


@function_tool(strict_mode=False)
async def get_vehicle_details(
    ctx: RunContextWrapper[ProbeContext],
    scope: Literal["one", "all"],
    mode: Literal["facts", "compare"],
    result_number: Annotated[int, Field(ge=1, le=3)] | None = None,
) -> str:
    """Read facts for one prior result or compare all current results."""
    return _record(
        ctx,
        "get_vehicle_details",
        {"scope": scope, "mode": mode, "result_number": result_number},
    )


@function_tool(strict_mode=False)
async def list_catalog_options(
    ctx: RunContextWrapper[ProbeContext],
    topic: Literal["cities", "vehicle_types", "fuels", "body_types", "makes"],
) -> str:
    """List the available values for one catalog topic."""
    return _record(ctx, "list_catalog_options", {"topic": topic})


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke-test semantic intent and scope selection without catalog access.")
    parser.add_argument("--model", action="append", dest="models", help="Groq model to test; repeat for multiple models")
    parser.add_argument("--delay-seconds", type=float, default=2.0)
    return parser.parse_args()


def _matches(expected: dict[str, Any], actual: dict[str, Any]) -> bool:
    return all(actual.get(name) == value for name, value in expected.items())


async def _run_case(model: OpenAIChatCompletionsModel, case: SmokeCase) -> tuple[bool, ProbeContext, float, int]:
    context = ProbeContext()
    agent = Agent[ProbeContext](
        name="Intent routing smoke",
        instructions=SYSTEM_PROMPT,
        model=model,
        model_settings=ModelSettings(temperature=0.0, tool_choice="auto", parallel_tool_calls=False),
        tools=[search_vehicles, get_vehicle_details, list_catalog_options],
        tool_use_behavior="stop_on_first_tool",
    )
    input_items: str | list[dict[str, str]] = case.utterance
    if case.has_previous_results:
        input_items = [
            {"role": "assistant", "content": PREVIOUS_RESULTS},
            {"role": "user", "content": case.utterance},
        ]

    started = perf_counter()
    result = await Runner.run(agent, input_items, context=context, max_turns=2)
    elapsed_ms = (perf_counter() - started) * 1000
    passed = context.tool == case.expected_tool and _matches(case.expected_arguments, context.arguments)
    return passed, context, elapsed_ms, result.context_wrapper.usage.total_tokens


async def _run(models: list[str], delay_seconds: float) -> bool:
    console = Console()
    client = AsyncOpenAI(
        api_key=settings.groq.api_keys[0].get_secret_value(),
        base_url=settings.groq.base_url,
    )
    all_passed = True
    try:
        for model_name in models:
            model = OpenAIChatCompletionsModel(model=model_name, openai_client=client)
            table = Table(title=f"Intent routing smoke - {model_name}")
            table.add_column("Case")
            table.add_column("Expected")
            table.add_column("Actual")
            table.add_column("Result")
            table.add_column("ms", justify="right")
            table.add_column("Tokens", justify="right")

            passed_count = 0
            for index, case in enumerate(CASES):
                if index and delay_seconds:
                    await asyncio.sleep(delay_seconds)
                try:
                    passed, context, elapsed_ms, tokens = await _run_case(model, case)
                    actual = f"{context.tool} {json.dumps(context.arguments, sort_keys=True)}"
                except Exception as error:  # noqa: BLE001 - show every model/case failure in one smoke run
                    passed = False
                    elapsed_ms = 0.0
                    tokens = 0
                    actual = f"{type(error).__name__}: {error}"
                passed_count += passed
                all_passed = all_passed and passed
                table.add_row(
                    case.name,
                    f"{case.expected_tool} {json.dumps(case.expected_arguments, sort_keys=True)}",
                    actual,
                    "PASS" if passed else "FAIL",
                    f"{elapsed_ms:,.0f}" if elapsed_ms else "-",
                    f"{tokens:,}" if tokens else "-",
                    style="green" if passed else "red",
                )

            console.print(table)
            console.print(f"{model_name}: {passed_count}/{len(CASES)} intents correct", style="bold")
    finally:
        await client.close()
    return all_passed


def main() -> None:
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure:
        reconfigure(encoding="utf-8")
    arguments = _arguments()
    models = arguments.models or [settings.groq.primary_model, *settings.groq.fallback_models]
    if not asyncio.run(_run(list(dict.fromkeys(models)), arguments.delay_seconds)):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
