import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

from rich.console import Console
from vehicle_search_agent.runner import VehicleSearchSession

from evals.evaluator.agent import case_mismatches, load_cases
from evals.evaluator.voice_metrics import build_voice_report, filter_counts, transcription_counts
from evals.reporting.core import print_report, prune_old_reports, report_paths
from evals.reporting.voice import format_percentage, markdown_voice_report
from evals.settings import DEFAULT_DELAY_SECONDS, DEFAULT_MIN_PASS_RATE, DEFAULT_VOICE_CASES_PATH

console = Console()


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate recorded voice cases through STT, the live agent, catalog search, and TTS."
    )
    parser.add_argument("--cases", type=Path, default=DEFAULT_VOICE_CASES_PATH)
    parser.add_argument("--case", action="append", dest="case_ids", help="Run only this case ID; repeat as needed")
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional JSON path; defaults to data/evaluation/<dataset>-<UTC timestamp>.json",
    )
    parser.add_argument("--min-pass-rate", type=float, default=DEFAULT_MIN_PASS_RATE)
    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=DEFAULT_DELAY_SECONDS,
        help="Pause between cases for provider rate limits",
    )
    return parser.parse_args()


async def evaluate_voice(
    cases: list[dict[str, Any]],
    *,
    dataset_directory: Path,
    delay_seconds: float = 0.0,
) -> list[dict[str, Any]]:
    run_id = uuid4().hex[:8]
    sessions: dict[str, VehicleSearchSession] = {}
    rows = []

    for case in cases:
        if rows and delay_seconds:
            await asyncio.sleep(delay_seconds)
        conversation_id = case.get("conversation_id", case["id"])
        session = sessions.setdefault(
            conversation_id,
            VehicleSearchSession(f"voice-eval-{run_id}-{conversation_id}"),
        )
        previous_ids = list(session.context.state.last_result_ids)
        reference = case["utterance"]
        audio_path = dataset_directory / case["audio"]
        transcript = ""
        try:
            audio = audio_path.read_bytes()
            received_at = perf_counter()
            result = await session.run_voice_turn(
                audio,
                filename=audio_path.name,
                recording_received_at=received_at,
            )
            transcript = result.transcript
            grounded = session.context.grounded_response
            routing_correct = result.action.value == case["expected_action"]
            problems, arguments_correct = case_mismatches(
                case,
                result,
                previous_ids,
                grounded.facts if grounded else (),
            )
            actual_filters = result.active_filters.model_dump(mode="json", exclude_none=True)
            rows.append(
                {
                    "id": case["id"],
                    "audio": case["audio"],
                    "audio_source": case.get("audio_source", "recorded"),
                    "reference_transcript": reference,
                    "transcript": transcript,
                    "transcription": transcription_counts(reference, transcript),
                    "passed": not problems,
                    "problems": problems,
                    "model": result.model_used,
                    "expected_action": case["expected_action"],
                    "action": result.action.value,
                    "routing_correct": routing_correct,
                    "arguments_correct": routing_correct and arguments_correct,
                    "expected_filters": case["expected_filters"],
                    "filters": actual_filters,
                    "filter_counts": filter_counts(case, actual_filters),
                    "result_ids": result.last_result_ids,
                    "response": result.spoken_response,
                    "timings_ms": result.metrics.model_dump(exclude_none=True),
                    "usage": result.usage.model_dump(exclude_none=True),
                }
            )
        except Exception as error:  # noqa: BLE001 - one failed recording must not stop the dataset run
            actual_filters = session.context.state.active_filters.model_dump(mode="json", exclude_none=True)
            rows.append(
                {
                    "id": case["id"],
                    "audio": case["audio"],
                    "audio_source": case.get("audio_source", "recorded"),
                    "reference_transcript": reference,
                    "transcript": transcript,
                    "transcription": transcription_counts(reference, transcript),
                    "passed": False,
                    "problems": [f"{type(error).__name__}: {error}"],
                    "model": str(session.agent.model.model),
                    "expected_action": case["expected_action"],
                    "action": None,
                    "routing_correct": False,
                    "arguments_correct": False,
                    "expected_filters": case["expected_filters"],
                    "filters": actual_filters,
                    "filter_counts": filter_counts(case, actual_filters),
                    "result_ids": session.context.state.last_result_ids,
                    "timings_ms": {},
                    "usage": {},
                }
            )
    return rows


def main() -> None:
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure:
        reconfigure(encoding="utf-8")

    arguments = _arguments()
    cases = load_cases(arguments.cases, arguments.case_ids)
    missing_audio = [case["audio"] for case in cases if not (arguments.cases.parent / case["audio"]).is_file()]
    if missing_audio:
        raise SystemExit(f"Missing voice recordings: {', '.join(missing_audio)}")

    rows = asyncio.run(
        evaluate_voice(
            cases,
            dataset_directory=arguments.cases.parent,
            delay_seconds=arguments.delay_seconds,
        )
    )
    generated_at = datetime.now(UTC)
    report = build_voice_report(rows, generated_at)
    print_report(report, console, title="Voice Pipeline Evaluation")
    console.print(
        "Transcript exact: "
        f"{format_percentage(report['transcription']['exact_match_rate'])}; "
        f"WER: {format_percentage(report['transcription']['word_error_rate'])}; "
        f"filter F1: {format_percentage(report['filter_extraction']['f1'])}"
    )

    json_path, markdown_path = report_paths(arguments.cases, generated_at, arguments.output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(markdown_voice_report(report, arguments.cases), encoding="utf-8")
    prune_old_reports(json_path.parent)
    console.print(f"Saved: {json_path}", style="dim")
    console.print(f"Saved: {markdown_path}", style="dim")

    if report["pass_rate"] < arguments.min_pass_rate:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
