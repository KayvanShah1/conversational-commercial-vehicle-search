# Evaluation report

## What is scored

`evals/evaluate_agent.py` sends each utterance through the real agent and
MotherDuck search path. It checks the expected action, active filters, changed
slots, result presence, previous-result preservation or exclusion, detail
record count, required response meaning, forbidden text, and grounded search
facts. Answers may be naturally rephrased; catalog values may not change.

The datasets are under `evals/`, not `data/`. Generated reports belong under
`data/evaluation/`.

## Latest live runs on 2026-09-03

- Core dataset: `evals/agent_cases.json`
- Core result: 27/27, 100%
- Core mean understanding: 1,083.62 ms
- Core mean search: 621.38 ms
- Core mean response generation: 1,265.38 ms on the three detail turns
- Core mean total: 1,793.79 ms
- Core mean tokens: 2,143.96
- Core mean estimated LLM list cost: INR 0.0460 per turn
- Variant dataset: `evals/vehicle_variant_cases.json`
- Variant result: 17/18, 94.4%
- Variant mean understanding: 1,680.80 ms
- Variant mean search: 797.50 ms
- Variant mean response generation: 4,007.81 ms on detail turns
- Variant mean total: 4,032.36 ms
- Variant mean tokens: 3,047.72
- Variant mean estimated LLM list cost: INR 0.0467 per turn
- Focused regression for search, more-options, all-option weights, and all
  details: 4/4, 100%
- Local suite: 90 passed, 1 opt-in integration skipped

Both complete runs used the live agent and MotherDuck search path. The first
Groq route was intermittently rate-limited; bounded key/model rotation found an
available Groq route and every case completed. The variant suite's one failure
was an evaluator vocabulary gap: the grounded answer said "listed in Delhi"
while the city concept accepted only "city", "located in", or "location". The
concept alternatives now include that natural phrasing; no agent fact, action,
filter, or result ID was wrong. The raw JSON reports are
`data/evaluation/latest_results.json` and
`data/evaluation/vehicle_variant_results.json`. Every new evaluation run also
writes a timestamped Markdown report, for example
`data/evaluation/vehicle_variant_cases-20260903T063119Z.md`.

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
- The full local suite passed: 85 passed, 1 opt-in integration skipped.
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
  --delay-seconds 10
```

Use `--case CASE_ID` repeatedly for a focused diagnosis. Do not combine selected
passes from repeated attempts into a claimed single-run score. By default, the
JSON and Markdown filenames use the dataset name and the same UTC timestamp.
Pass `--output` only when a stable JSON filename is intentionally required.

One real voice turn (use only audio you are authorized to send to the configured
STT provider):

```powershell
uv run --package agents python evals/measure_voice_latency.py `
  --audio path/to/authorized-sample.wav
```

This writes `data/evaluation/voice_latency_results.json` and a timestamped
`voice-latency-*.md` report.

## Latency boundary

Text turns record understanding, search or lookup, optional grounded-response
generation, and total time. Voice turns additionally record STT, TTS, and
speech-end-to-audio-ready time. With Streamlit's default microphone composer,
the server timestamp begins when the completed browser recording reaches the
app, not at the browser's exact speech-stop event. Because the TTS API returns
a complete WAV rather than a stream, "audio ready" is when that full playable
WAV exists. The UI and logs label this boundary directly; exact browser
speech-stop to first streamed byte requires a custom client event and streaming
transport.

## Usage and cost boundary

Per turn, the harness stores LLM request count, input, cached-input, output,
reasoning, and total tokens. Voice turns additionally store audio duration and
TTS characters. Estimated INR is based on public list prices for the successful
model route plus configured STT/TTS list rates. It is not an invoice, excludes
database/hosting spend, and may exceed actual free-tier spend.
