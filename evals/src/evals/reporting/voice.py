from pathlib import Path
from typing import Any

from evals.reporting.core import display_path, percentage

TIMING_LABELS = {
    "stt_ms": "STT",
    "understanding_ms": "Understanding",
    "search_ms": "Search",
    "response_ms": "Response",
    "tts_ms": "TTS",
    "recording_received_to_audio_ready_ms": "Recording received → audio ready",
    "total_ms": "Total",
}


def format_percentage(value: float | None) -> str:
    return f"{value:.1f}%" if value is not None else "N/A"


def markdown_voice_report(report: dict[str, Any], dataset: Path) -> str:
    transcription = report["transcription"]
    filters = report["filter_extraction"]
    lines = [
        "# Voice pipeline evaluation",
        "",
        f"- Generated: {report['generated_at_utc']}",
        f"- Dataset: `{display_path(dataset)}`",
        f"- End-to-end pass rate: **{report['pass_rate']:.1f}% ({report['passed']}/{report['total']})**",
        "",
        "## Quality",
        "",
        "| Metric | Result |",
        "| --- | ---: |",
        f"| Routing accuracy | {format_percentage(report['accuracy']['routing']['rate'])} |",
        f"| Argument/state accuracy | {format_percentage(report['accuracy']['arguments']['rate'])} |",
        f"| Transcript exact-match rate | {format_percentage(transcription['exact_match_rate'])} |",
        f"| Word error rate (lower is better) | {format_percentage(transcription['word_error_rate'])} |",
        f"| Character error rate (lower is better) | {format_percentage(transcription['character_error_rate'])} |",
        f"| Filter precision | {format_percentage(filters['precision'])} |",
        f"| Filter recall | {format_percentage(filters['recall'])} |",
        f"| Filter F1 | {format_percentage(filters['f1'])} |",
        "",
        "## Latency",
        "",
        "| Stage | Mean | p50 | p95 |",
        "| --- | ---: | ---: | ---: |",
    ]
    for name, label in TIMING_LABELS.items():
        values = report["latency_ms"].get(name)
        if values is None:
            lines.append(f"| {label} | N/A | N/A | N/A |")
        else:
            lines.append(
                f"| {label} | {values['mean']:,.2f} ms | "
                f"{values['p50']:,.2f} ms | {values['p95']:,.2f} ms |"
            )

    lines.extend(
        [
            "",
            "## Cases",
            "",
            "| Case | Reference | Transcript | WER | Expected | Actual | Result | Total | Est. INR | Problems |",
            "| --- | --- | --- | ---: | --- | --- | --- | ---: | ---: | --- |",
        ]
    )
    for row in report["cases"]:
        reference_words = row["transcription"]["reference_words"]
        word_error_rate = percentage(row["transcription"]["word_edits"], reference_words)
        cost = row["usage"].get("estimated_list_cost_inr")
        reference = row["reference_transcript"].replace("|", "\\|")
        transcript = row["transcript"].replace("|", "\\|")
        problems = "; ".join(row["problems"]).replace("|", "\\|") or "-"
        lines.append(
            f"| {row['id']} | {reference} | {transcript} | {format_percentage(word_error_rate)} | "
            f"{row['expected_action']} | {row['action'] or 'error'} | {'PASS' if row['passed'] else 'FAIL'} | "
            f"{row['timings_ms'].get('total_ms', '-')} | {f'{cost:.4f}' if cost is not None else '-'} | "
            f"{problems} |"
        )

    lines.extend(
        [
            "",
            (
                "The end-to-end pass rate checks the executed action, filters, results, and grounded response. "
                "Transcript exact match, WER, and CER are reported separately because harmless wording "
                "differences can still produce the correct downstream behavior."
            ),
            "",
            (
                "Recording-received latency starts when each completed WAV is handed to the voice runner and "
                "ends when the complete synthesized response WAV has been generated. It excludes recording, "
                "upload, browser rendering, and playback."
            ),
            "",
        ]
    )
    return "\n".join(lines)
