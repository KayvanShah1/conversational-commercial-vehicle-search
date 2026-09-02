# Evaluation report

## What is scored

`evals/evaluate_agent.py` sends each utterance through the real agent and
MotherDuck search path. It checks the expected action, active filters, changed
slots, result presence, previous-result preservation or exclusion, detail
record count, required response meaning, forbidden text, and grounded search
facts. Answers may be naturally rephrased; catalog values may not change.

The datasets are under `evals/`, not `data/`. Generated reports belong under
`data/evaluation/`.

## Verified focused run

- Timestamp: 2026-09-02T19:32:39.594085+00:00
- Dataset: `evals/vehicle_variant_cases.json`
- Result: 18/18, 100%
- Mean understanding: 1,519.29 ms
- Mean search: 441.79 ms
- Mean total: 1,960.88 ms
- Local suite at the same checkpoint: 65 passed, 1 opt-in integration skipped

The original JSON was overwritten during later experiments. The concise
archived record in `data/evaluation/verified_variant_summary.json` was recovered
from the retained command output and contains the original per-case model and
total latency values. It is labeled as a recovered summary rather than passed
off as the original JSON.

## Confirmation run on 2026-09-03

The exact recovered code was rerun against the same 18 cases. The first nine
cases all passed, including search, pagination, all-option weights, full vehicle
details, and multiple size/category variants. After that point every configured
free-tier model returned HTTP 429, so the raw run ended at 9/18. None of the
nine failures produced a logic mismatch; they failed before an action or filter
could be returned.

This is an availability limitation, not evidence for claiming a fresh 100%
score. For a live evaluator run, use provider capacity with a sufficient quota
or wait for the free-tier pools to reset.

## Final submission smoke on 2026-09-03

- Ruff passed across `agents`, `app`, `evals`, and `tests`.
- The full local suite passed: 75 passed, 1 opt-in integration skipped.
- Live STT transcribed the sample correctly in 843.71 ms.
- Live TTS produced a 172,870-byte WAV in 648.80 ms.
- A four-turn live text session passed a neutral greeting, a Mumbai heavy-
  machinery search, a one-lookup payload answer for all three options, and a
  refusal to expose raw catalog data or SQL.
- A final combined synthetic voice turn transcribed correctly in 231.74 ms,
  then exhausted every LLM fallback with HTTP 429. It is therefore recorded as
  a failed end-to-end attempt, not an audio-ready measurement.

## Commands

Core conversational suite:

```powershell
uv run --package agents python evals/evaluate_agent.py --delay-seconds 10
```

Focused variants:

```powershell
uv run --package agents python evals/evaluate_agent.py `
  --cases evals/vehicle_variant_cases.json `
  --delay-seconds 10 `
  --output data/evaluation/vehicle_variant_results.json
```

Use `--case CASE_ID` repeatedly for a focused diagnosis. Do not combine selected
passes from repeated attempts into a claimed single-run score.

## Latency boundary

Text turns record understanding, search or lookup, optional grounded-response
generation, and total time. Voice turns additionally record STT, TTS, and
speech-end-to-audio-ready time. Because the current TTS API returns a complete
WAV rather than a stream, "audio ready" is the first point at which browser
playback can start; it is not time to the first streamed audio chunk.
