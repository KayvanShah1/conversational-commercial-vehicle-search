# Architecture and technical decisions

This is the concise, submission-facing design record. The wiki contains the deeper [architecture rationale](https://github.com/KayvanShah1/conversational-commercial-vehicle-search/wiki/Architecture-and-Technical-Decisions), [agent behavior walkthrough](https://github.com/KayvanShah1/conversational-commercial-vehicle-search/wiki/Agent-Behavior-and-Grounding), and [evaluation and observability guide](https://github.com/KayvanShah1/conversational-commercial-vehicle-search/wiki/Evaluation-and-Observability).

## Seven identifiable components

| System component | Current implementation | Production seam |
| --- | --- | --- |
| Voice interface | Streamlit microphone, text fallback, result/state display, and audio playback | Product client with streaming media |
| Speech to text | File-based Groq Whisper request | Streaming STT with confidence and endpointing |
| Understanding | One Agents SDK agent with three typed tools | Capacity-backed model behind the same schemas |
| Catalog and search | Parameterized MotherDuck queries and deterministic ranking | Indexed search service with bounded connections |
| Response and TTS | Grounded composer, validator, and batched WAV synthesis | Streaming response and TTS gateway |
| Conversation state | Typed state plus SDK `SQLiteSession` | Redis or another concurrent state store |
| Evaluation | Behavior-based case suites and structured timings | Pinned CI evaluations and production telemetry |

These are responsibility boundaries, not seven agents or a serial model chain.

## Decisions at a glance

| Decision | Chosen | Rejected | Main trade-off |
| --- | --- | --- | --- |
| Catalog access | Typed tool arguments plus application-owned parameterized SQL | Generated SQL or a general database tool | New hard filters require schema and query changes, but constraints remain testable and raw data stays inaccessible. |
| Agent topology | One bounded agent with search, details, and catalog-options tools | Intent, selector, response, and critic agent hierarchy | Avoids extra model latency, tokens, hand-offs, and disagreement for three domain operations. |
| Response grounding | Deterministic facts and fallback, with validated natural rephrasing where useful | Prompt-only grounding or natural generation for every search | Comparison and detail answers remain conversational without allowing invented or reordered catalog values. |
| Voice | Recorded audio → STT → text agent/search → TTS → WAV | Opaque speech-to-speech model | The cascade is slower, but transcript, filters, records, stage latency, and failures remain inspectable. |
| Database lifecycle | One scoped read-only MotherDuck connection per catalog operation | Process-global connection | Ownership is safe for concurrent Streamlit sessions; production should replace repeated setup with a bounded pool or read service. |

## Correctness boundaries

The model reasons at two seams:

1. choose one of the three tools and extract typed arguments;
2. optionally phrase a detail or comparison answer over returned records.

Application code owns SQL construction, hard-filter enforcement, ranking, cross-turn slot merging, catalog facts, and numeric validation. Ordinary grounded searches stop after the tool and use deterministic composition. If an optional natural answer drops, reorders, or invents required facts, the deterministic fallback is shown.

If a no-tool response names a current result, the runner retries once with the details tool required. This keeps general questions tool-free without allowing listing-specific claims from conversation prose alone. Invalid tool arguments have a three-attempt repair limit.

## Code organization and retained safeguards

The implementation is grouped by capability: `agent/`, `models/`, `tools/`, `search/`, `response/`, `runner/`, and `voice/`. Packages expose small public APIs without generic one-use service, repository, or presenter classes.

| Safeguard | Why it remains |
| --- | --- |
| One `OperationLogContext` | Supplies monotonic duration and structured fields without duplicate timing wrappers. |
| TTS batching | The provider limits each request to 200 characters, so compatible WAV chunks are stitched in application code. |
| Bounded model fallback | The demo can rotate configured Groq keys/models while preserving one Agents SDK model interface. |
| Result invariant check | Every returned row is rechecked against active hard filters before display. |
| Grounded-response validator | Catalog identifiers and numeric values cannot be changed by natural rephrasing. |

Deliberately absent: generated SQL, a raw database tool, multi-agent routing, generic repositories, prompt-encoded vehicle inventory, expected-answer matching, and a framework wrapper around the SDK session.

## Ranking

Search applies hard filters first; ranking only orders valid candidates. Purpose fit carries 30%, while verified papers, budget proximity, lower mileage, and condition carry 15% each and newer year carries 10%. Signals unavailable for a query are zeroed and the remaining weights are normalized. The UI exposes the numeric breakdown for each returned listing.

## Fallback and failure behavior

Each turn starts on the last successful model route. A retryable failure makes one bounded pass through configured Groq keys and models. STT and TTS independently remember their last successful key and rotate on rate limits. If every route fails, the UI reports a recoverable error rather than inventing a vehicle.

## Production priorities

At 100,000 conversations per month, provider capacity and long-tail model latency are expected to fail before a 1,000-row catalog query. The upgrade order is:

1. purchase defined-capacity model routes and add circuit-breaker telemetry;
2. stream STT and TTS while retaining the typed text-agent boundary;
3. replace SQLite history with a concurrent store and retention limits;
4. add a bounded catalog connection pool or read service and cache low-cardinality options;
5. run pinned-model evaluations in CI with a separate canary set for provider changes.

Current pass rates, timings, token use, and estimated cost live only in [Evaluation](EVALUATION.md) so volatile evidence has one source of truth. The wiki explains the speech-latency boundary, trace grouping, cost interpretation, and longer-form production rationale.

## Reviewer quick answers

- **If STT hears “S” instead of “Ace”:** exact filtering returns no match instead of silently substituting a model. Production would add catalog-aware normalization with a confidence-gated confirmation step.
- **Why these results rank first:** the UI's numeric ranking table is the evidence; the prose is not.
- **What gets replaced first:** free-provider routing becomes a capacity-backed gateway behind the existing Agents SDK model interface.
- **Where to recover the first 200 ms:** warm or pool catalog connections; detail turns can also skip natural rephrasing when a deterministic requested-field response is sufficient.
