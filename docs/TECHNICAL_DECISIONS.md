# Architecture and technical decisions

This is the concise submission-facing design record. The wiki contains the deeper [architecture narrative](https://github.com/KayvanShah1/conversational-commercial-vehicle-search/wiki/Architecture-and-Technical-Decisions) and [agent behavior walkthrough](https://github.com/KayvanShah1/conversational-commercial-vehicle-search/wiki/Agent-Behavior-and-Grounding).

## Seven identifiable components

| System component | Implementation | Hidden complexity | Production replacement |
| --- | --- | --- | --- |
| Voice interface | `app/main.py` Streamlit microphone, text fallback, result/state display, audio playback | Browser capture and reruns | Product web client with streaming media |
| Speech to text | `voice.py:transcribe_audio` | Multipart audio and provider timing | Streaming STT with noisy-audio adaptation |
| Understanding | One Agents SDK agent with typed tools | Intent choice, slot extraction, correction | Larger capacity model with the same schemas |
| Catalog and search | `search.py` plus MotherDuck | Parameterized filters, ranking, invariant checks | Search service with replicas and indexes |
| Response and TTS | `response.py` plus `voice.py` | Grounded composition, value validation, WAV batching | Streaming response and TTS gateway |
| Conversation state | Typed `ConversationState` plus SDK `SQLiteSession` | Slot merging and result references | Redis or durable session service |
| Evaluation and latency | `evals.evaluate_agent` and structured operation logs | Semantic checks and stage timing | CI evaluation service plus observability |

## Code organization and quality review

The implementation is separated by failure boundary rather than by framework pattern. The largest files remain cohesive modules: `tools.py` validates model-facing inputs, `search.py` owns parameterized queries and ranking, `response.py` owns grounded composition, and `runner.py` owns turns, state, retries, and telemetry. Splitting these into one-use classes would add navigation without isolating another responsibility.

| Review concern | Resolution |
| --- | --- |
| Repeated API-key checks | Pydantic settings validate and deduplicate Groq keys; OpenRouter is normalized once as an optional provider. |
| Unused logging wrappers | One `OperationLogContext` records monotonic duration and structured fields across catalog, model, tool, STT, TTS, and turn operations. |
| Tool-selector or critic agent | Not added. Three typed operations do not justify another model call or state hand-off. |
| Generic service/repository layer | Not added. Search is the only MotherDuck consumer and owns its parameterized queries directly. |
| Process-global database connection | Not used. Each catalog operation owns one scoped read-only connection and reuses it for that operation. |
| Prompt and schema duplication | The prompt explains *when* to use a tool; schemas and docstrings describe *which values* are accepted. |
| TTS batching | Retained because the provider caps each request at 200 characters; application code chunks text and stitches compatible WAV responses. |
| Model fallback adapter | Retained because the SDK accepts one model interface while the demo needs bounded key, model, and provider failover. |
| Rechecking database results | Retained as the hard-filter invariant that detects a violated user constraint before a result is shown. |

Deliberately absent: generated SQL, a raw database tool, multi-agent routing, generic repositories, prompt-encoded vehicle inventories, expected-answer matching, and a framework-specific wrapper around the conversation session.

## Decision 1: typed tools and deterministic SQL

**Chosen:** the model identifies intent and supplies typed slot arguments;
application code builds parameterized SQL, applies hard filters, ranks rows, and
checks every returned record against the filters.

**Rejected:** asking the model to generate SQL or giving it a general database
tool.

**Why:** budgets, fuel, and cities are hard constraints. Deterministic query
construction is easier to test and prevents data exfiltration, arbitrary SQL,
and silent constraint relaxation. The cost is that new filters require a schema
and query change.

## Decision 2: one bounded agent, not an agent hierarchy

**Chosen:** one Vivi agent chooses among three typed tools. Small code rules are
used only for hard invariants such as literal fuel/body/category terms, previous
result references, and the three-attempt invalid-tool bound.

**Rejected:** separate intent, slot-extraction, tool-selector, response, and
critic agents.

**Why:** a multi-agent chain adds serial model latency, tokens, failure modes,
and state hand-offs to a demo whose domain has three operations. The current
seams remain replaceable without turning each seam into another model call.

## Decision 3: deterministic facts with optional natural rephrasing

**Chosen:** tools create a grounded fallback and an ordered set of allowed
catalog values. The model may rephrase them naturally. Code rejects missing,
reordered, or newly invented numeric facts and uses the fallback instead.

**Rejected:** prompt-only grounding and a global `stop_on_first_tool` policy.

**Why:** prompt-only instructions do not enforce zero invention. Always stopping
at the first tool is safe but makes comparison and capability follow-ups sound
mechanical. Validation preserves a conversational voice while keeping the
catalog boundary explicit. It cannot prove that subjective buying advice is
optimal; it only proves the factual values are grounded.

The latency mitigation already implemented is to stop immediately on ordinary
grounded search results. Detail and comparison turns use one post-tool model
pass so Vivi can speak naturally over typed catalog facts. The prompt permits
only one catalog tool per turn, and code validates the final values before they
reach the user.

## Where the agent reasons

The model reasons only at two bounded seams: choosing one of three tools and
extracting its typed arguments, then phrasing a detail/comparison answer over
returned records. SQL construction, hard-filter enforcement, ranking,
cross-turn slot merging, catalog facts, and factual validation remain
deterministic.

GPT-OSS may report reasoning tokens even without an explicit reasoning-effort
setting. Increasing reasoning effort globally is not assumed to improve this
system: it adds latency and tokens and can increase tool-call variability. A
larger reasoning budget is justified only for a measured failure class such as
a grounded multi-record explanation, and only if the evaluation gain offsets
the latency and schema-error cost.

## Decision 4: cascaded voice pipeline

**Chosen:** file-based STT, text agent/search, then TTS.

**Rejected:** a speech-to-speech model.

**Why:** the cascade keeps the transcript, slots, executed filters, records, and
latency for every stage inspectable during evaluation. It is slower than a
streaming speech-to-speech system but much easier to debug and defend. The first
production latency change would be streaming STT/TTS without changing the agent
or search interfaces.

## Decision 5: scoped MotherDuck connections

**Chosen:** open one read-only connection for each catalog operation, reuse it
for all SQL inside that operation, then close it through the shared context
manager.

**Rejected:** a process-global DuckDB connection passed through every layer.

**Why:** one global connection is fragile across concurrent Streamlit sessions
and couples the agent to database lifecycle. Per-operation ownership is obvious
and safe for the demo. At higher load it would be replaced by a bounded pool or
a catalog service rather than opening unlimited connections.

## Model fallback and failure behavior

The agent starts each turn on the last successful route. On a retryable failure,
it makes one bounded pass through every configured Groq key and model before the
optional OpenRouter Gemma routes. Speech requests likewise remember the last
successful Groq key and rotate on HTTP 429. This protects later turns from
repeatedly hitting a known-exhausted key, but free models do not guarantee
independent upstream capacity. The UI reports a recoverable error instead of
inventing a vehicle when every route fails.

## What breaks first at 100,000 conversations per month

The first bottleneck is external model capacity: serial LLM calls, free-tier
rate limits, and long-tail latency. Priority order:

1. Purchase defined-capacity provider tiers, add circuit breakers, and monitor
   per-provider tokens, rupee cost, availability, and p95 latency.
2. Stream STT and TTS and keep deterministic searches on the one-model-call
   path when no post-tool reasoning is required.
3. Replace local SQLite sessions with Redis or another concurrent state store;
   cap session lifetime and payload size.
4. Put catalog access behind a bounded connection pool/read service, add indexes
   for common filters, and cache low-cardinality catalog options.
5. Run the evaluation set in CI against a pinned model and maintain a separate
   canary set for provider/model changes.

## Usage and cost telemetry

Each turn records LLM requests, input, cached-input, output, reasoning, and
total tokens from the Agents SDK. Voice turns also record input-audio seconds
and TTS characters. The UI and evaluation reports estimate equivalent list
cost using the successful model route; actual free-tier spend can be zero.

The 27-case live core run averaged 2,143.96 tokens and INR 0.0460 of estimated
LLM list cost per text turn. At that observed mix, 100,000 text turns would be
about INR 4,605 for the LLM portion only. Voice, database, hosting, retries, and
production discounts are separate. USD values use an explicitly documented
INR 95.43 exchange-rate assumption, so this is a reproducible estimate rather
than a provider-billing claim.

Cached-input tokens are displayed as context reuse, not operating-system RAM.
Conversation memory itself is the small typed slot/result state plus the SDK's
SQLite history. Process-memory profiling is not part of the required metrics
and should be added under load testing rather than conflated with token usage.

## Q&A defence

### If STT hears “S” instead of “Ace”

The transcript reaches the same intent/slot path. If “S” is treated as a model
filter, the deterministic search returns no exact matches; it does not silently
substitute Ace. The missing production seam is a catalog-aware normalization
step between STT and tool execution that can propose likely makes/models and
ask for confirmation when confidence is low. It should not silently rewrite a
user constraint.

### Why these three ranked first

The UI's **Why these ranked first** table exposes the numeric
`RankingBreakdown` for each returned listing: purpose 30%, papers 15%, budget
15%, mileage 15%, condition 15%, and year 10%. Signals unavailable for a query
are zeroed and the remaining weights are normalized. This is the data behind
the ordering, not a prose rationale generated after the fact.

### First production replacement

Replace the free-provider routing/capacity layer first. The agent consumes the
Agents SDK model interface and returns typed tool arguments, so a purchased
provider or internal gateway can replace `FallbackModel` without changing SQL,
ranking, response validation, or the UI contract.

### First 200 ms to win back

In the latest 27-case core run, understanding averaged 1,083.62 ms and catalog
search/lookup averaged 621.38 ms; detail response generation averaged 1,265.38
ms on the three turns that used it. The first broadly available ~200 ms is in
catalog connection setup: keep a bounded warm read-only connection pool or put
the catalog behind a small read service. Detail turns can save more by using a
deterministic requested-field composer when natural rephrasing is unnecessary.

## Speech-end latency boundary

Voice turns record `speech_end_to_audio_ready_ms`. With Streamlit's default
audio-enabled chat input, the server first sees the recording after the browser
has completed and uploaded it, so the start timestamp is server receipt of that
completed recording. The end timestamp is when the full synthesized WAV is
available for playback. This is a useful, repeatable server-side proxy, but it
excludes browser upload time and is not first streamed audio bytes. Exact
browser speech-stop to first-byte measurement requires a custom client event
and streaming audio transport; that is the first voice-interface production
upgrade, not something hidden by the reported number.
