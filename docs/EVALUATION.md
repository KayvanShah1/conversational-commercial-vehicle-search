# Evaluation

Vivi is evaluated through the real agent and MotherDuck search path. Cases define expected behavior without requiring one exact sentence, so the agent may speak naturally while catalog facts and user constraints remain testable.

For the extended rationale and failure taxonomy, see the wiki's [evaluation and observability](https://github.com/KayvanShah1/conversational-commercial-vehicle-search/wiki/Evaluation-and-Observability) page.

## Latest results

| Suite | Cases | Passed | Pass rate |
| --- | ---: | ---: | ---: |
| Core conversation | 28 | 28 | **100%** |
| Vehicle variants | 18 | 18 | **100%** |
| Recorded voice pipeline | 6 | 5 | **83.3%** |
| All suites | 52 | 51 | **98.1%** |

All three complete runs were executed on 2026-09-06 through the live model, MotherDuck, and, for voice cases, STT and TTS paths. The combined pass rate exceeds the assignment's 90% target. Generated JSON and Markdown reports are retained locally under `data/evaluation/` and excluded from Git.

One expanded voice case remains failed in the report: the spoken city was transcribed and extracted as `Bangalore`, while the catalog and expected filter use `Bengaluru`. No focused rerun was substituted into the score, and the expectation was not weakened to hide the mismatch.

With the documented 10-second rate-limit delay, the 52 cases took about 10 minutes 54 seconds of evaluator runtime: 5 minutes 37 seconds for the core suite, 3 minutes 55 seconds for vehicle variants, and 1 minute 22 seconds for voice. Case processing totalled about 2 minutes 42 seconds; the remaining time was the deliberate delay between cases. Provider latency and rate limits will make future runs vary.

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

The expanded voice suite intentionally retains one failed case and therefore writes its report before exiting with status 1 against the default 90% per-suite threshold. The combined 52-case result remains above 90%; the threshold and expected filter are left unchanged so the known failure stays visible.

The voice manifest and recordings live together under `evals/datasets/voice/`. Add a case by supplying its WAV, reference utterance, expected action, and expected filters. Use `--case CASE_ID` repeatedly for a focused run.

The report includes transcript exact match, word error rate (WER), character error rate (CER), routing and argument accuracy, filter precision/recall/F1, end-to-end pass rate, cost, and mean, p50, and p95 latency. Stage timing covers STT, understanding, search or lookup, an optional validated follow-up model response, TTS, total time, and `recording_received_to_audio_ready_ms`. Ordinary search and catalog replies use deterministic grounded composition within total time, so their separate response stage is `N/A`.

With Streamlit’s built-in microphone composer, the server receives audio only after browser recording and upload complete. The measurement therefore starts when the completed recording reaches the server and ends when the full synthesized WAV has been generated. It is a repeatable server-side proxy, not exact browser speech-stop to first streamed audio byte or playback.

### Recorded voice runs

On 2026-09-06, two TTS-generated WAV files and four human recordings were sent through the live STT, agent, MotherDuck search, grounded response, and TTS path. Five cases met all declared expectations. All six selected the expected action; the failed payload case extracted `Bangalore` instead of the catalog's canonical `Bengaluru` and consequently returned no results.

| Request | Result | Audio | STT | Understanding | Search | Response | TTS | Recording received → audio ready | Estimated list cost |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| CNG mini truck under ₹6 lakh in Pune for city delivery | Pass | 4.96 s | 0.65 s | 0.86 s | 5.00 s | N/A | 4.05 s | **10.61 s** | ₹0.6301 |
| Diesel tipper under ₹12 lakh in Mumbai with verified papers | Pass | 6.00 s | 0.33 s | 0.81 s | 0.23 s | N/A | 1.78 s | **3.20 s** | ₹0.2999 |
| Human Hinglish: verified pickup under ₹12 lakh in Hyderabad | Pass | 5.58 s | 0.40 s | 0.81 s | 0.30 s | N/A | 4.60 s | **6.15 s** | ₹0.6655 |
| General diesel-versus-CNG buying question | Pass | 8.22 s | 0.50 s | 2.12 s | N/A | N/A | 1.04 s | **3.71 s** | ₹0.2853 |
| Hinglish: at least one-tonne payload in Bengaluru | **Fail** | 5.44 s | 0.37 s | 0.82 s | 1.02 s | N/A | 1.44 s | **3.77 s** | ₹0.3090 |
| Available cities | Pass | 2.63 s | 0.32 s | 0.96 s | 0.22 s | N/A | 2.98 s | **4.50 s** | ₹0.3977 |
| Mean |  | 5.47 s | 0.43 s | 1.06 s | 1.36 s | N/A | 2.65 s | **5.32 s** | ₹0.4313 |

TTS was the largest mean voice stage. The first catalog query also paid a 5.00-second cold-connection cost; later search and catalog operations completed in 0.22–1.02 seconds. Warm or pooled MotherDuck connections and streaming speech remain the first production latency improvements, as described in [technical decisions](TECHNICAL_DECISIONS.md#production-priorities).

Ordinary search and catalog replies use deterministic grounded composition within total time rather than a separate response timer. Details and comparisons report a response stage when a validated follow-up model call runs.

The two synthetic inputs make baseline measurements repeatable, while four human recordings add English and Hinglish coverage. Three transcripts matched exactly. The provider rendered the two Hinglish requests largely in Devanagari, contributing to 69.1% aggregate WER and 33.88% CER even when their meaning was mostly preserved. Downstream filter precision, recall, and F1 were each 93.8%; routing remained 100%. This is why transcript similarity, routing, filter accuracy, and task success are reported separately. The general buying case is routing-focused and verifies that no catalog tool is called; it does not score the completeness of the buying advice. Recording or synthetic-audio generation happened before the measured boundary and is not included.

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
- the six-case live voice suite completed every provider stage and retained one application-level city-alias failure

Provider-backed evaluation and voice tests are intentionally separate from the default unit suite because they consume external quota and transmit configured inputs.

## Known boundaries

1. Free-tier provider pools can all return HTTP 429. Bounded route rotation improves demo resilience but does not guarantee capacity.
2. The current voice endpoint returns complete WAV files, so the measured endpoint is generated WAV bytes rather than first streamed bytes or browser playback.
3. Natural-response validation guarantees grounded numeric and catalog facts; it does not prove that subjective buying advice is globally optimal.
4. Free-text city aliases are not canonicalized. In the expanded voice run, `Bangalore` did not match the catalog's `Bengaluru` value.
