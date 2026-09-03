from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from uuid import uuid4

from rich.console import Console
from rich.table import Table
from vehicle_search_agent.runner import VehicleSearchSession

sys.stdout.reconfigure(encoding="utf-8")
console = Console()
DEFAULT_CASES = Path("evals/agent_cases.json")
DEFAULT_OUTPUT_DIR = Path("data/evaluation")


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate live agent intent, slots, results, and latency.")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--case", action="append", dest="case_ids", help="Run only this case ID; repeat as needed")
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional JSON path; defaults to data/evaluation/<dataset>-<UTC timestamp>.json",
    )
    parser.add_argument("--min-pass-rate", type=float, default=90.0)
    parser.add_argument("--delay-seconds", type=float, default=0.0, help="Pause between cases for provider rate limits")
    return parser.parse_args()


def _mismatches(case: dict, result, previous_ids: list[str], grounded_facts: tuple[str, ...]) -> list[str]:
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


async def evaluate(cases: list[dict], *, delay_seconds: float = 0.0) -> list[dict]:
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


def _print_report(rows: list[dict]) -> float:
    table = Table(title="Vehicle Search Agent Evaluation")
    table.add_column("Case")
    table.add_column("Action")
    table.add_column("Model")
    table.add_column("Result")
    table.add_column("Total ms", justify="right")
    table.add_column("Tokens", justify="right")
    table.add_column("Est. INR", justify="right")
    table.add_column("Mismatch")

    for row in rows:
        table.add_row(
            row["id"],
            row["action"] or "error",
            row["model"],
            "PASS" if row["passed"] else "FAIL",
            str(row["timings_ms"].get("total_ms", "-")),
            str(row["usage"].get("total_tokens", "-")),
            (
                f"{row['usage']['estimated_list_cost_inr']:.4f}"
                if row["usage"].get("estimated_list_cost_inr") is not None
                else "-"
            ),
            "; ".join(row["problems"]),
            style="green" if row["passed"] else "red",
        )
    console.print(table)

    pass_rate = 100 * sum(row["passed"] for row in rows) / len(rows)
    console.print(f"Pass rate: {pass_rate:.1f}% ({sum(row['passed'] for row in rows)}/{len(rows)})", style="bold")
    for stage in ("understanding_ms", "search_ms", "response_ms", "total_ms"):
        values = [row["timings_ms"][stage] for row in rows if stage in row["timings_ms"]]
        if values:
            console.print(f"Mean {stage}: {mean(values):.2f}")
    for metric in (
        "llm_requests",
        "input_tokens",
        "cached_input_tokens",
        "output_tokens",
        "reasoning_tokens",
        "total_tokens",
        "estimated_list_cost_inr",
    ):
        values = [row["usage"][metric] for row in rows if metric in row["usage"]]
        if values:
            console.print(f"Mean {metric}: {mean(values):.4f}")
    return pass_rate


def _markdown_report(report: dict, dataset: Path) -> str:
    lines = [
        "# Vehicle search agent evaluation",
        "",
        f"- Generated: {report['generated_at_utc']}",
        f"- Dataset: `{dataset.as_posix()}`",
        f"- Pass rate: **{report['pass_rate']:.1f}% ({report['passed']}/{report['total']})**",
        "",
        "## Mean turn telemetry",
        "",
        "| Metric | Mean |",
        "| --- | ---: |",
    ]
    for name, value in report["mean_timings_ms"].items():
        label = name.removesuffix("_ms").replace("_", " ").title()
        lines.append(f"| {label} | {value:,.2f} ms |")
    for name, value in report["mean_usage"].items():
        unit = "INR" if name == "estimated_list_cost_inr" else "tokens"
        precision = 4 if unit == "INR" else 2
        label = name.replace("_", " ").title().replace("Llm", "LLM").replace("Inr", "INR")
        if name == "llm_requests":
            unit = "requests"
        lines.append(f"| {label} | {value:,.{precision}f} {unit} |")

    lines.extend(
        [
            "",
            "## Cases",
            "",
            "| Case | Action | Model route | Result | Total ms | Tokens | Est. INR | Problems |",
            "| --- | --- | --- | --- | ---: | ---: | ---: | --- |",
        ]
    )
    for row in report["cases"]:
        cost = row["usage"].get("estimated_list_cost_inr")
        problems = "; ".join(row["problems"]).replace("|", "\\|") or "-"
        lines.append(
            f"| {row['id']} | {row['action'] or 'error'} | {row['model']} | "
            f"{'PASS' if row['passed'] else 'FAIL'} | {row['timings_ms'].get('total_ms', '-')} | "
            f"{row['usage'].get('total_tokens', '-')} | {f'{cost:.4f}' if cost is not None else '-'} | "
            f"{problems} |"
        )

    lines.extend(
        [
            "",
            "## Cost method",
            "",
            (
                "Equivalent list-price cost uses the successful model route for each LLM call. "
                "Actual free-tier spend may be zero. Voice turns additionally include STT audio duration and TTS characters."
            ),
            "The USD/INR conversion assumption is documented in `docs/TECHNICAL_DECISIONS.md`.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    arguments = _arguments()
    cases = json.loads(arguments.cases.read_text(encoding="utf-8"))
    if arguments.case_ids:
        cases = [case for case in cases if case["id"] in arguments.case_ids]
    rows = asyncio.run(evaluate(cases, delay_seconds=arguments.delay_seconds))
    pass_rate = _print_report(rows)

    generated_at = datetime.now(UTC)
    report = {
        "generated_at_utc": generated_at.isoformat(),
        "pass_rate": pass_rate,
        "passed": sum(row["passed"] for row in rows),
        "total": len(rows),
        "mean_timings_ms": {
            stage: mean(values)
            for stage in ("understanding_ms", "search_ms", "response_ms", "total_ms")
            if (values := [row["timings_ms"][stage] for row in rows if stage in row["timings_ms"]])
        },
        "mean_usage": {
            metric: mean(values)
            for metric in (
                "llm_requests",
                "input_tokens",
                "cached_input_tokens",
                "output_tokens",
                "reasoning_tokens",
                "total_tokens",
                "estimated_list_cost_inr",
            )
            if (values := [row["usage"][metric] for row in rows if metric in row["usage"]])
        },
        "cases": rows,
    }
    timestamp = f"{generated_at:%Y%m%dT%H%M%SZ}"
    output = arguments.output or DEFAULT_OUTPUT_DIR / f"{arguments.cases.stem}-{timestamp}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    console.print(f"Saved: {output}", style="dim")
    markdown_output = output.parent / f"{arguments.cases.stem}-{timestamp}.md"
    markdown_output.write_text(_markdown_report(report, arguments.cases), encoding="utf-8")
    console.print(f"Saved: {markdown_output}", style="dim")

    if pass_rate < arguments.min_pass_rate:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
