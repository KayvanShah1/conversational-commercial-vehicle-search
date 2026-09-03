from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from rich.console import Console
from vehicle_search_agent.runner import VehicleSearchSession

from evals.reporting import build_report, markdown_report, print_report, report_paths
from evals.settings import DEFAULT_CASES_PATH, DEFAULT_DELAY_SECONDS, DEFAULT_MIN_PASS_RATE

console = Console()


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate live agent intent, slots, results, and latency.")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES_PATH)
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


def _mismatches(
    case: dict[str, Any],
    result: Any,
    previous_ids: list[str],
    grounded_facts: tuple[str, ...],
) -> list[str]:
    actual_filters = result.active_filters.model_dump(mode="json", exclude_none=True)
    response = result.spoken_response.casefold().replace("’", "'")
    problems = []
    if result.action.value != case["expected_action"]:
        problems.append(f"action={result.action.value}")
    if any(actual_filters.get(name) != value for name, value in case["expected_filters"].items()):
        problems.append(f"filters={actual_filters}")
    unexpected = set(actual_filters) - set(case["expected_filters"]) - {
        "vehicle_category",
        "weight_class",
        "purpose",
    }
    if unexpected:
        problems.append(f"unexpected_filters={sorted(unexpected)}")
    if "expect_results" in case and bool(result.last_result_ids) != case["expect_results"]:
        problems.append(f"result_count={len(result.last_result_ids)}")
    expected_changed = case.get("expected_changed_fields")
    if expected_changed is not None and [field.value for field in result.changed_fields] != expected_changed:
        problems.append(f"changed_fields={[field.value for field in result.changed_fields]}")
    if case.get("preserve_result_ids") and result.last_result_ids != previous_ids:
        problems.append("result_ids_changed")
    if case.get("new_result_ids") and set(result.last_result_ids).intersection(previous_ids):
        problems.append("results_repeated")
    expected_detail_count = case.get("expected_detail_count")
    if expected_detail_count is not None and len(grounded_facts) != expected_detail_count:
        problems.append(f"detail_count={len(grounded_facts)}")
    expected_any = [text.casefold() for text in case.get("expected_response_contains_any", [])]
    if expected_any and not any(text in response for text in expected_any):
        problems.append("response_missing_expected_text")
    expected_all = [text.casefold() for text in case.get("expected_response_contains_all", [])]
    if any(text not in response for text in expected_all):
        problems.append("response_missing_required_text")
    expected_concepts = case.get("expected_response_concepts", [])
    if any(not any(term.casefold() in response for term in alternatives) for alternatives in expected_concepts):
        problems.append("response_missing_expected_concept")
    if result.action.value == "search" and result.last_result_ids:
        missing_facts = [fact for fact in grounded_facts if fact.casefold() not in response]
        if missing_facts:
            problems.append(f"grounded_facts_missing={len(missing_facts)}")
    forbidden = [text.casefold() for text in case.get("response_must_not_contain", [])]
    if any(text in response for text in forbidden):
        problems.append("response_contains_forbidden_text")
    return problems


async def evaluate(cases: list[dict[str, Any]], *, delay_seconds: float = 0.0) -> list[dict[str, Any]]:
    run_id = uuid4().hex[:8]
    sessions: dict[str, VehicleSearchSession] = {}
    rows = []

    for case in cases:
        if rows and delay_seconds:
            await asyncio.sleep(delay_seconds)
        conversation_id = case.get("conversation_id", case["id"])
        session = sessions.setdefault(
            conversation_id,
            VehicleSearchSession(f"eval-{run_id}-{conversation_id}"),
        )
        previous_ids = list(session.context.state.last_result_ids)
        try:
            result = await session.run_text_turn(case["utterance"])
            grounded = session.context.grounded_response
            problems = _mismatches(case, result, previous_ids, grounded.facts if grounded else ())
            rows.append(
                {
                    "id": case["id"],
                    "passed": not problems,
                    "problems": problems,
                    "model": result.model_used,
                    "action": result.action.value,
                    "filters": result.active_filters.model_dump(mode="json", exclude_none=True),
                    "result_ids": result.last_result_ids,
                    "response": result.spoken_response,
                    "timings_ms": result.metrics.model_dump(exclude_none=True),
                    "usage": result.usage.model_dump(exclude_none=True),
                }
            )
        except Exception as error:  # noqa: BLE001 - one failed case must not stop the evaluation run
            rows.append(
                {
                    "id": case["id"],
                    "passed": False,
                    "problems": [f"{type(error).__name__}: {error}"],
                    "model": str(session.agent.model.model),
                    "action": None,
                    "filters": session.context.state.active_filters.model_dump(mode="json", exclude_none=True),
                    "result_ids": session.context.state.last_result_ids,
                    "timings_ms": {},
                    "usage": {},
                }
            )

    return rows


def _load_cases(path: Path, case_ids: list[str] | None) -> list[dict[str, Any]]:
    cases = json.loads(path.read_text(encoding="utf-8"))
    if case_ids:
        cases = [case for case in cases if case["id"] in case_ids]
    if not cases:
        raise SystemExit("No evaluation cases selected.")
    return cases


def main() -> None:
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure:
        reconfigure(encoding="utf-8")

    arguments = _arguments()
    rows = asyncio.run(
        evaluate(
            _load_cases(arguments.cases, arguments.case_ids),
            delay_seconds=arguments.delay_seconds,
        )
    )
    generated_at = datetime.now(UTC)
    report = build_report(rows, generated_at)
    print_report(report, console)

    json_path, markdown_path = report_paths(arguments.cases, generated_at, arguments.output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(markdown_report(report, arguments.cases), encoding="utf-8")
    console.print(f"Saved: {json_path}", style="dim")
    console.print(f"Saved: {markdown_path}", style="dim")

    if report["pass_rate"] < arguments.min_pass_rate:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
