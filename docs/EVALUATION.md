# Evaluation

Vivi is evaluated through the real agent and MotherDuck search path. Cases define expected behavior without requiring one exact sentence, so the agent may speak naturally while catalog facts and user constraints remain testable.

For the extended rationale and failure taxonomy, see the wiki's [evaluation and observability](https://github.com/KayvanShah1/conversational-commercial-vehicle-search/wiki/Evaluation-and-Observability) page.

## Latest results

| Suite | Cases | Passed | Pass rate |
| --- | ---: | ---: | ---: |
| Core conversation | 28 | 28 | **100%** |
| Vehicle variants | 18 | 18 | **100%** |
| Recorded voice pipeline | 3 | 3 | **100%** |
| All suites | 49 | 49 | **100%** |

All three complete runs were executed on 2026-09-06 through the live model, MotherDuck, and, for voice cases, STT and TTS paths. Generated JSON and Markdown reports are retained locally under `data/evaluation/` and excluded from Git.

All cases passed in their complete suite runs; no focused rerun was substituted into any score.

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
| Understanding | 1,166.86 ms | 1,049.62 ms |
| Catalog search or lookup | 613.93 ms | 691.56 ms |
| Grounded response generation¹ | 5,744.22 ms | 4,761.02 ms |
| Total | 2,344.51 ms | 3,588.23 ms |
| Tokens | 2,188.89 | 3,058.67 |
| Estimated LLM list cost | INR 0.0378 | INR 0.0496 |

¹ Response-generation means are calculated only for turns that use the optional post-tool natural-language pass. Straight grounded searches stop after deterministic composition.

## Run the suites

Run the primary suite first:

```powershell
uv run --package evals python -m evals.evaluator.agent --delay-seconds 10
```

Then run the breadth suite:

```powershell
uv run --package evals python -m evals.evaluator.agent `
  --cases evals/datasets/vehicle_variant_cases.json `
  --delay-seconds 10
```

Use `--case CASE_ID` repeatedly for focused diagnosis. Do not combine selected passes from different attempts into a claimed single-run score.

Each run writes local, Git-ignored JSON and Markdown reports under `data/evaluation/`. By default, both filenames contain the dataset name and the same UTC timestamp; `--output` is available when a stable JSON filename is intentionally required. The evaluator retains the five newest runs and removes older report files automatically, including reports written with custom names.

## Voice latency

Run the recorded voice suite only with audio you are authorized to send to the configured speech provider:

```powershell
uv run --package evals python -m evals.evaluator.voice --delay-seconds 10
```

The voice manifest and recordings live together under `evals/datasets/voice/`. Add a case by supplying its WAV, reference utterance, expected action, and expected filters. Use `--case CASE_ID` repeatedly for a focused run.

The report includes transcript exact match, word error rate (WER), character error rate (CER), routing and argument accuracy, filter precision/recall/F1, end-to-end pass rate, cost, and mean, p50, and p95 latency. Stage timing covers STT, understanding, search or lookup, an optional validated follow-up model response, TTS, total time, and `recording_received_to_audio_ready_ms`. Ordinary search and catalog replies use deterministic grounded composition within total time, so their separate response stage is `N/A`.

With Streamlit’s built-in microphone composer, the server receives audio only after browser recording and upload complete. The measurement therefore starts when the completed recording reaches the server and ends when the full synthesized WAV has been generated. It is a repeatable server-side proxy, not exact browser speech-stop to first streamed audio byte or playback.

### Recorded voice runs

On 2026-09-06, two TTS-generated WAV files and one human-recorded Hinglish request were sent through the live STT, agent, MotherDuck search, grounded response, and TTS path. All three selected the search action, extracted every expected filter, and returned grounded results.

| Request | Audio | STT | Understanding | Search | Response | TTS | Recording received → audio ready | Estimated list cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| CNG mini truck under ₹6 lakh in Pune for city delivery | 4.96 s | 0.76 s | 0.90 s | 5.01 s | N/A | 3.99 s | **10.71 s** | ₹0.6302 |
| Diesel tipper under ₹12 lakh in Mumbai with verified papers | 6.00 s | 0.29 s | 0.81 s | 0.30 s | N/A | 1.65 s | **3.09 s** | ₹0.2999 |
| Human Hinglish: verified pickup under ₹12 lakh in Hyderabad | 5.58 s | 0.39 s | 1.01 s | 0.30 s | N/A | 5.69 s | **7.42 s** | ₹0.6684 |
| Mean | 5.51 s | 0.48 s | 0.91 s | 1.87 s | N/A | 3.78 s | **7.07 s** | ₹0.5329 |

TTS was the largest mean voice stage. The first catalog query also paid a 5.01-second cold-connection cost; the next two searches completed in about 0.30 seconds. Warm or pooled MotherDuck connections and streaming speech remain the first production latency improvements, as described in [technical decisions](TECHNICAL_DECISIONS.md#production-priorities).

Ordinary search and catalog replies use deterministic grounded composition within total time rather than a separate response timer. Details and comparisons report a response stage when a validated follow-up model call runs.

The two synthetic inputs make baseline measurements repeatable, while the human recording adds realistic Hinglish coverage. The speech provider returned the Hinglish transcript largely in Devanagari, producing 65.0% aggregate WER across the three cases despite 100% downstream filter precision, recall, and F1. This is why transcript similarity and task success are reported separately. Recording or synthetic-audio generation happened before the measured boundary and is not included.

## Usage and cost

Per turn, the harness stores:

- LLM request count
- input, cached-input, output, reasoning, and total tokens
- successful provider and model route
- audio duration and synthesized characters for voice turns
- equivalent public-list-price estimates in USD and INR

The estimate is not an invoice. Free-tier spend can be zero, and database, hosting, retries, discounts, and production pricing are outside the calculation. The USD/INR assumption and provider references are documented in [sources](SOURCES.md). The wiki's [evaluation and observability](https://github.com/KayvanShah1/conversational-commercial-vehicle-search/wiki/Evaluation-and-Observability) page explains how to interpret these metrics and inspect grouped OpenAI traces.

## Local verification

The latest local verification reported:

- 69 tests passed
- 1 live MotherDuck integration test skipped by default
- Repository-wide Ruff check passed
- Streamlit AppTest rendered the conversation, result, state, and metric surfaces
- the three-case live voice suite completed STT, agent, catalog, grounding, and TTS successfully

Provider-backed evaluation and voice tests are intentionally separate from the default unit suite because they consume external quota and transmit configured inputs.

## Known boundaries

1. Free-tier provider pools can all return HTTP 429. Bounded route rotation improves demo resilience but does not guarantee capacity.
2. The current voice endpoint returns complete WAV files, so the measured endpoint is generated WAV bytes rather than first streamed bytes or browser playback.
3. Natural-response validation guarantees grounded numeric and catalog facts; it does not prove that subjective buying advice is globally optimal.
