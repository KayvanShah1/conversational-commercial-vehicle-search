# Evaluation report

## What is scored

`evals/evaluate_agent.py` sends each utterance through the real agent and
MotherDuck search path. It checks the expected action, active filters, changed
slots, result presence, previous-result preservation or exclusion, detail
record count, required response meaning, forbidden text, and grounded search
facts. Answers may be naturally rephrased; catalog values may not change.

The datasets are under `evals/`, not `data/`. Generated reports belong under
`data/evaluation/`.

## Complete live run on 2026-09-03

- Core dataset: `evals/agent_cases.json`
- Core result: 23/23, 100%
- Core mean understanding: 750.55 ms
- Core mean search: 471.29 ms
- Core mean total: 1,168.83 ms
- Variant dataset: `evals/vehicle_variant_cases.json`
- Variant result: 18/18, 100%
- Variant mean understanding: 725.21 ms
- Variant mean search: 444.67 ms
- Variant mean total: 1,169.72 ms
- Local suite: 83 passed, 1 opt-in integration skipped

Both complete runs used the live agent and MotherDuck search path. The first
Groq route was intermittently rate-limited; bounded key/model rotation found an
available Groq route and every case completed. The raw reports are
`data/evaluation/latest_results.json` and
`data/evaluation/vehicle_variant_results.json`.

## Earlier provider-limited confirmation

The exact recovered code was rerun against the same 18 cases. The first nine
cases all passed, including search, pagination, all-option weights, full vehicle
details, and multiple size/category variants. After that point every configured
free-tier model returned HTTP 429, so the raw run ended at 9/18. None of the
nine failures produced a logic mismatch; they failed before an action or filter
could be returned.

That earlier result remains useful evidence of the free-tier availability risk,
but it has been superseded by the complete live runs above.

## Final submission smoke on 2026-09-03

- Ruff passed across `agents`, `app`, `evals`, and `tests`.
- The full local suite passed: 83 passed, 1 opt-in integration skipped.
- Live STT transcribed the sample correctly in 843.71 ms.
- Live TTS produced a 172,870-byte WAV in 648.80 ms.
- A four-turn live text session passed a neutral greeting, a Mumbai heavy-
  machinery search, a one-lookup payload answer for all three options, and a
  refusal to expose raw catalog data or SQL.
- A final combined synthetic voice turn transcribed correctly in 231.74 ms,
  then exhausted every LLM fallback with HTTP 429. It is therefore recorded as
  a failed end-to-end attempt, not an audio-ready measurement.
- After Groq key rotation was added, the exact `my bidget is 20 lakhs` case
  passed its executable evaluation: action `search`, `budget_max=2000000`,
  grounded results present, 1/1.

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
