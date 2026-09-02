from __future__ import annotations

import asyncio
import sys
from uuid import uuid4

from rich.console import Console
from rich.prompt import Prompt
from vehicle_search_agent.runner import VehicleSearchSession

sys.stdout.reconfigure(encoding="utf-8")
console = Console()


async def chat() -> None:
    session = VehicleSearchSession(f"text-chat-{uuid4().hex[:8]}")
    console.print("Text chat with Vivi", style="bold green")
    console.print("Type 'quit' to leave.", style="dim")

    while True:
        message = (await asyncio.to_thread(Prompt.ask, "[bold cyan]YOU[/]")).strip()
        if message.casefold() in {"quit", "exit"}:
            return
        if not message:
            continue

        result = await session.run_text_turn(message)
        console.print("VIVI>", result.spoken_response, style="green", markup=False)
        console.print(
            "STATE>",
            result.active_filters.model_dump_json(exclude_none=True),
            style="dim",
            markup=False,
        )


if __name__ == "__main__":
    asyncio.run(chat())
