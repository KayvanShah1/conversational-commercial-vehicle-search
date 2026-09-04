# Evaluation

Vivi is evaluated through the real agent and MotherDuck search path. Cases define expected behavior without requiring one exact sentence, so the agent may speak naturally while catalog facts and user constraints remain testable.

For the extended rationale and failure taxonomy, see the wiki's [evaluation and observability](https://github.com/KayvanShah1/conversational-commercial-vehicle-search/wiki/Evaluation-and-Observability) page.

## Latest results

| Suite | Cases | Passed | Pass rate |
| --- | ---: | ---: | ---: |
| Core conversation | 28 | 28 | **100%** |
| Vehicle variants | 18 | 18 | **100%** |
| Combined | 46 | 46 | **100%** |

Both complete runs were executed on 2026-09-05 through the live agent and MotherDuck path. Generated JSON and Markdown reports are retained locally under `data/evaluation/` and excluded from Git.

## What is evaluated

Every case can assert one or more of the following:

- selected action or tool
- active filters and changed slots
- result presence or an expected zero-result outcome
- preservation or exclusion of previous result IDs
- detail record count
- required response concepts and forbidden text
- factual grounding of returned search records
- latency, model route, token usage, and estimated cost telemetry

This separates expected behavior from exact prose. Rephrasing is allowed; changing catalog values or silently violating constraints is not.

## Evaluation suites

### Core conversation

[`evals/datasets/agent_cases.json`](../evals/datasets/agent_cases.json) contains 28 cases covering:

- greetings and bounded general questions
- natural budget, fuel, body, city, payload, and use-case constraints
- intent and typed slot extraction
- search, catalog options including flattened purpose tags, and vehicle-detail actions
- cross-turn correction and preference changes
- previous-result references
- zero-result handling
- unsafe requests for raw data or SQL

### Vehicle variants

[`evals/datasets/vehicle_variant_cases.json`](../evals/datasets/vehicle_variant_cases.json) contains 18 cases covering:

- light, intermediate, medium, and heavy vehicles
- mini truck, pickup, and rigid truck categories
- open, flatbed, box, container, tipper, tanker, and reefer bodies
- diesel and CNG
- budget ranges and payload-unit conversion
- pagination and requests for more options
- all-result weight lookup and complete vehicle details
- general commercial-vehicle questions

## Mean turn telemetry

| Metric | Core | Vehicle variants |
| --- | ---: | ---: |
| Understanding | 1,017.39 ms | 788.56 ms |
| Catalog search or lookup | 432.65 ms | 459.73 ms |
| Grounded response generation¹ | 1,752.86 ms | 4,127.22 ms |
| Total | 1,606.45 ms | 2,858.60 ms |
| Tokens | 2,218.61 | 3,230.17 |
| Estimated LLM list cost | INR 0.0381 | INR 0.0534 |

¹ Response-generation means are calculated only for turns that use the optional post-tool natural-language pass. Straight grounded searches stop after deterministic composition.

## Run the suites

Run the primary suite first:

```powershell
uv run --package evals python -m evals.evaluate_agent --delay-seconds 10
```

Then run the breadth suite:

```powershell
uv run --package evals python -m evals.evaluate_agent `
  --cases evals/datasets/vehicle_variant_cases.json `
  --delay-seconds 10
```

Use `--case CASE_ID` repeatedly for focused diagnosis. Do not combine selected passes from different attempts into a claimed single-run score.

Each run writes local, Git-ignored JSON and Markdown reports under `data/evaluation/`. By default, both filenames contain the dataset name and the same UTC timestamp; `--output` is available when a stable JSON filename is intentionally required. The evaluator retains the five newest runs and removes older report files automatically, including reports written with custom names.

## Voice latency

Run one real voice turn with an audio sample you are authorized to send to the configured STT provider:

```powershell
uv run --package evals python -m evals.measure_voice_latency `
  --audio path/to/authorized-sample.wav
```

The report includes STT, understanding, search or lookup, optional response generation, TTS, total time, and `speech_end_to_audio_ready_ms`.

With Streamlit’s built-in microphone composer, the server receives audio only after browser recording and upload complete. The measurement therefore starts when the completed recording reaches the server and ends when the full synthesized WAV is ready for playback. It is a repeatable server-side proxy, not exact browser speech-stop to first streamed audio byte.

## Usage and cost

Per turn, the harness stores:

- LLM request count
- input, cached-input, output, reasoning, and total tokens
- successful provider and model route
- audio duration and synthesized characters for voice turns
- equivalent public-list-price estimates in USD and INR

The estimate is not an invoice. Free-tier spend can be zero, and database, hosting, retries, discounts, and production pricing are outside the calculation. The USD/INR assumption and provider references are documented in [architecture and technical decisions](TECHNICAL_DECISIONS.md#usage-and-cost-telemetry) and [sources](SOURCES.md).

## Local verification

The latest local verification reported:

- 90 unit tests passed
- 1 live MotherDuck integration test skipped by default
- Ruff passed across source, app, evaluations, and tests
- Streamlit AppTest rendered the conversation, result, state, and metric surfaces
- live STT and TTS smoke checks produced valid transcript and WAV output

Provider-backed evaluation and voice tests are intentionally separate from the default unit suite because they consume external quota and transmit configured inputs.

## Known boundaries

1. Free-tier provider pools can all return HTTP 429. Bounded route rotation improves demo resilience but does not guarantee capacity.
2. The current voice endpoint returns complete WAV files, so the measured endpoint is playable audio rather than first streamed bytes.
3. Natural-response validation guarantees grounded numeric and catalog facts; it does not prove that subjective buying advice is globally optimal.
