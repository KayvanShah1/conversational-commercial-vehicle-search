from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from rich.console import Console
from vehicle_search_agent.runner import VehicleSearchSession

console = Console()


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Measure one real voice turn and save its telemetry.")
    parser.add_argument("--audio", type=Path, required=True, help="WAV audio containing one user utterance")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/evaluation/voice_latency_results.json"),
    )
    return parser.parse_args()


async def _measure(audio_path: Path) -> dict:
    audio = audio_path.read_bytes()
    session = VehicleSearchSession(f"voice-eval-{uuid4().hex[:8]}")
    received_at = perf_counter()
    result = await session.run_voice_turn(
        audio,
        filename=audio_path.name,
        speech_ended_at=received_at,
    )
    return {
        "transcript": result.transcript,
        "action": result.action.value,
        "model": result.model_used,
        "timings_ms": result.metrics.model_dump(exclude_none=True),
        "usage": result.usage.model_dump(exclude_none=True),
    }


def _markdown(report: dict, audio_path: Path) -> str:
    rows = [
        f"| {name.replace('_', ' ').title()} | {value:,.2f} ms |"
        for name, value in report["result"]["timings_ms"].items()
    ]
    return "\n".join(
        [
            "# Voice latency evaluation",
            "",
            f"- Generated: {report['generated_at_utc']}",
            f"- Audio: `{audio_path.as_posix()}`",
            f"- Transcript: {report['result']['transcript']}",
            f"- Model route: `{report['result']['model']}`",
            "",
            "## Per-turn latency",
            "",
            "| Stage | Time |",
            "| --- | ---: |",
            *rows,
            "",
            "The speech-end boundary is server receipt of the completed browser recording; ",
            "audio ready is the complete WAV returned for playback. See `docs/TECHNICAL_DECISIONS.md`.",
            "",
        ]
    )


def main() -> None:
    arguments = _arguments()
    result = asyncio.run(_measure(arguments.audio))
    generated_at = datetime.now(UTC)
    report = {"generated_at_utc": generated_at.isoformat(), "result": result}

    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    markdown_path = arguments.output.parent / f"voice-latency-{generated_at:%Y%m%dT%H%M%SZ}.md"
    markdown_path.write_text(_markdown(report, arguments.audio), encoding="utf-8")

    console.print_json(data=report)
    console.print(f"Saved: {arguments.output}", style="dim")
    console.print(f"Saved: {markdown_path}", style="dim")


if __name__ == "__main__":
    main()
