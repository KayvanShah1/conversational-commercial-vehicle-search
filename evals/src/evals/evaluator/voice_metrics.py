import math
import re
from datetime import datetime
from statistics import mean, median
from typing import Any
from unicodedata import normalize

from evals.evaluator.agent import ALLOWED_INFERRED_FILTERS
from evals.reporting.core import build_report, percentage

VOICE_TIMING_FIELDS = (
    "stt_ms",
    "understanding_ms",
    "search_ms",
    "response_ms",
    "tts_ms",
    "recording_received_to_audio_ready_ms",
    "total_ms",
)


def _tokens(text: str) -> list[str]:
    return re.findall(r"\w+", normalize("NFKC", text).casefold(), flags=re.UNICODE)


def _edit_distance(reference: list[str], hypothesis: list[str]) -> int:
    previous = list(range(len(hypothesis) + 1))
    for reference_index, reference_item in enumerate(reference, start=1):
        current = [reference_index]
        for hypothesis_index, hypothesis_item in enumerate(hypothesis, start=1):
            substitution = previous[hypothesis_index - 1] + (reference_item != hypothesis_item)
            current.append(
                min(
                    previous[hypothesis_index] + 1,
                    current[hypothesis_index - 1] + 1,
                    substitution,
                )
            )
        previous = current
    return previous[-1]


def transcription_counts(reference: str, transcript: str) -> dict[str, int | bool]:
    reference_words = _tokens(reference)
    transcript_words = _tokens(transcript)
    reference_characters = list(" ".join(reference_words))
    transcript_characters = list(" ".join(transcript_words))
    return {
        "exact": reference_words == transcript_words,
        "word_edits": _edit_distance(reference_words, transcript_words),
        "reference_words": len(reference_words),
        "character_edits": _edit_distance(reference_characters, transcript_characters),
        "reference_characters": len(reference_characters),
    }


def filter_counts(case: dict[str, Any], actual_filters: dict[str, Any]) -> dict[str, int]:
    expected = case["expected_filters"]
    actual = {
        name: value
        for name, value in actual_filters.items()
        if name in expected or name not in ALLOWED_INFERRED_FILTERS
    }
    true_positives = sum(actual.get(name) == value for name, value in expected.items())
    false_negatives = len(expected) - true_positives
    false_positives = sum(name not in expected or expected[name] != value for name, value in actual.items())
    return {"true_positives": true_positives, "false_positives": false_positives, "false_negatives": false_negatives}


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def build_voice_report(rows: list[dict[str, Any]], generated_at: datetime) -> dict[str, Any]:
    report = build_report(rows, generated_at)
    word_edits = sum(row["transcription"]["word_edits"] for row in rows)
    reference_words = sum(row["transcription"]["reference_words"] for row in rows)
    character_edits = sum(row["transcription"]["character_edits"] for row in rows)
    reference_characters = sum(row["transcription"]["reference_characters"] for row in rows)
    exact_matches = sum(row["transcription"]["exact"] for row in rows)
    report["transcription"] = {
        "exact_match_rate": percentage(exact_matches, len(rows)),
        "exact_matches": exact_matches,
        "word_error_rate": percentage(word_edits, reference_words),
        "word_edits": word_edits,
        "reference_words": reference_words,
        "character_error_rate": percentage(character_edits, reference_characters),
        "character_edits": character_edits,
        "reference_characters": reference_characters,
    }

    filter_totals = {
        name: sum(row["filter_counts"][name] for row in rows)
        for name in ("true_positives", "false_positives", "false_negatives")
    }
    true_positives = filter_totals["true_positives"]
    precision = percentage(true_positives, true_positives + filter_totals["false_positives"])
    recall = percentage(true_positives, true_positives + filter_totals["false_negatives"])
    filter_count = true_positives + filter_totals["false_positives"] + filter_totals["false_negatives"]
    f1 = 0.0 if filter_count else None
    if precision is not None and recall is not None and precision + recall:
        f1 = 2 * precision * recall / (precision + recall)
    report["filter_extraction"] = {
        **filter_totals,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }

    report["latency_ms"] = {}
    for field in VOICE_TIMING_FIELDS:
        values = [float(row["timings_ms"][field]) for row in rows if field in row["timings_ms"]]
        if values:
            report["latency_ms"][field] = {
                "mean": mean(values),
                "p50": median(values),
                "p95": _percentile(values, 0.95),
            }
    return report
