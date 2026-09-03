from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any

from rich.console import Console
from rich.table import Table

from evals.settings import PROJECT_ROOT, REPORTS_DIR

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


def build_report(rows: list[dict[str, Any]], generated_at: datetime) -> dict[str, Any]:
    passed = sum(row["passed"] for row in rows)
    return {
        "generated_at_utc": generated_at.isoformat(),
        "pass_rate": 100 * passed / len(rows),
        "passed": passed,
        "total": len(rows),
        "mean_timings_ms": _mean_fields(rows, "timings_ms", TIMING_FIELDS),
        "mean_usage": _mean_fields(rows, "usage", USAGE_FIELDS),
        "cases": rows,
    }


def report_paths(dataset: Path, generated_at: datetime, output: Path | None) -> tuple[Path, Path]:
    timestamp = f"{generated_at:%Y%m%dT%H%M%SZ}"
    json_path = output or REPORTS_DIR / f"{dataset.stem}-{timestamp}.json"
    return json_path, json_path.parent / f"{dataset.stem}-{timestamp}.md"


def print_report(report: dict[str, Any], console: Console) -> None:
    table = Table(title="Vehicle Search Agent Evaluation")
    table.add_column("Case")
    table.add_column("Action")
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
    console.print(
        f"Pass rate: {report['pass_rate']:.1f}% ({report['passed']}/{report['total']})",
        style="bold",
    )
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


def _display_path(path: Path) -> str:
    try:
        return path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.as_posix()
