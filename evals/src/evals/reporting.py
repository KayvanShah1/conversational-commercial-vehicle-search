import json
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any

from rich.console import Console
from rich.table import Table

from evals.settings import PROJECT_ROOT, REPORT_RETENTION_COUNT, REPORTS_DIR

TIMING_FIELDS = ("understanding_ms", "search_ms", "response_ms", "total_ms")
USAGE_FIELDS = (
    "llm_requests",
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "reasoning_tokens",
    "total_tokens",
    "estimated_list_cost_inr",
)
ACCURACY_LABELS = (
    ("Routing accuracy", "routing"),
    ("Tool-only accuracy", "tool_only"),
    ("No-tool accuracy", "no_tool"),
    ("Argument/state accuracy", "arguments"),
    ("End-to-end pass rate", "end_to_end"),
)


def build_report(rows: list[dict[str, Any]], generated_at: datetime) -> dict[str, Any]:
    passed = sum(row["passed"] for row in rows)
    tool_rows = [row for row in rows if row["expected_action"] != "conversation"]
    no_tool_rows = [row for row in rows if row["expected_action"] == "conversation"]
    return {
        "generated_at_utc": generated_at.isoformat(),
        "pass_rate": 100 * passed / len(rows),
        "passed": passed,
        "total": len(rows),
        "accuracy": {
            "routing": _score(rows, "routing_correct"),
            "tool_only": _score(tool_rows, "routing_correct"),
            "no_tool": _score(no_tool_rows, "routing_correct"),
            "arguments": _score(tool_rows, "arguments_correct"),
            "end_to_end": _score(rows, "passed"),
        },
        "mean_timings_ms": _mean_fields(rows, "timings_ms", TIMING_FIELDS),
        "mean_usage": _mean_fields(rows, "usage", USAGE_FIELDS),
        "cases": rows,
    }


def report_paths(dataset: Path, generated_at: datetime, output: Path | None) -> tuple[Path, Path]:
    timestamp = f"{generated_at:%Y%m%dT%H%M%SZ}"
    json_path = output or REPORTS_DIR / f"{dataset.stem}-{timestamp}.json"
    return json_path, json_path.parent / f"{dataset.stem}-{timestamp}.md"


def prune_old_reports(directory: Path) -> None:
    report_runs: dict[str, list[Path]] = {}
    for path in directory.iterdir():
        if path.suffix == ".json":
            try:
                timestamp = json.loads(path.read_text(encoding="utf-8")).get("generated_at_utc")
            except (json.JSONDecodeError, OSError):
                continue
        elif path.suffix == ".md":
            generated_line = next(
                (line for line in path.read_text(encoding="utf-8").splitlines() if line.startswith("- Generated: ")),
                "",
            )
            timestamp = generated_line.removeprefix("- Generated: ")
        else:
            continue
        if not timestamp:
            continue
        report_runs.setdefault(timestamp, []).append(path)

    for timestamp in sorted(report_runs, reverse=True)[REPORT_RETENTION_COUNT:]:
        for path in report_runs[timestamp]:
            path.unlink()


def print_report(report: dict[str, Any], console: Console) -> None:
    table = Table(title="Vehicle Search Agent Evaluation")
    table.add_column("Case")
    table.add_column("Expected")
    table.add_column("Actual")
    table.add_column("Model")
    table.add_column("Result")
    table.add_column("Total ms", justify="right")
    table.add_column("Tokens", justify="right")
    table.add_column("Est. INR", justify="right")
    table.add_column("Mismatch")

    for row in report["cases"]:
        cost = row["usage"].get("estimated_list_cost_inr")
        table.add_row(
            row["id"],
            row["expected_action"],
            row["action"] or "error",
            row["model"],
            "PASS" if row["passed"] else "FAIL",
            str(row["timings_ms"].get("total_ms", "-")),
            str(row["usage"].get("total_tokens", "-")),
            f"{cost:.4f}" if cost is not None else "-",
            "; ".join(row["problems"]),
            style="green" if row["passed"] else "red",
        )

    console.print(table)
    accuracy_table = Table(title="Accuracy summary")
    accuracy_table.add_column("Metric")
    accuracy_table.add_column("Score", justify="right")
    for label, key in ACCURACY_LABELS:
        score = report["accuracy"][key]
        accuracy_table.add_row(label, _format_score(score))
    console.print(accuracy_table)
    for name, value in report["mean_timings_ms"].items():
        console.print(f"Mean {name}: {value:.2f}")
    for name, value in report["mean_usage"].items():
        console.print(f"Mean {name}: {value:.4f}")


def markdown_report(report: dict[str, Any], dataset: Path) -> str:
    lines = [
        "# Vehicle search agent evaluation",
        "",
        f"- Generated: {report['generated_at_utc']}",
        f"- Dataset: `{_display_path(dataset)}`",
        f"- End-to-end pass rate: **{report['pass_rate']:.1f}% ({report['passed']}/{report['total']})**",
        "",
        "## Accuracy",
        "",
        "| Metric | Score |",
        "| --- | ---: |",
    ]
    for label, key in ACCURACY_LABELS:
        score = report["accuracy"][key]
        lines.append(f"| {label} | {_format_score(score)} |")

    lines.extend(
        [
            "",
            "## Mean turn telemetry",
            "",
            "| Metric | Mean |",
            "| --- | ---: |",
        ]
    )
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
            "| Case | Expected | Actual | Model route | Result | Total ms | Tokens | Est. INR | Problems |",
            "| --- | --- | --- | --- | --- | ---: | ---: | ---: | --- |",
        ]
    )
    for row in report["cases"]:
        cost = row["usage"].get("estimated_list_cost_inr")
        problems = "; ".join(row["problems"]).replace("|", "\\|") or "-"
        lines.append(
            f"| {row['id']} | {row['expected_action']} | {row['action'] or 'error'} | {row['model']} | "
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


def _mean_fields(
    rows: list[dict[str, Any]],
    section: str,
    fields: tuple[str, ...],
) -> dict[str, float]:
    means = {}
    for field in fields:
        values = [row[section][field] for row in rows if field in row[section]]
        if values:
            means[field] = mean(values)
    return means


def _score(rows: list[dict[str, Any]], field: str) -> dict[str, float | int | None]:
    correct = sum(bool(row[field]) for row in rows)
    total = len(rows)
    return {
        "rate": 100 * correct / total if total else None,
        "correct": correct,
        "total": total,
    }


def _format_score(score: dict[str, Any]) -> str:
    if not score["total"]:
        return "N/A (0 cases)"
    return f"{score['rate']:.1f}% ({score['correct']}/{score['total']})"


def _display_path(path: Path) -> str:
    try:
        return path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.as_posix()
