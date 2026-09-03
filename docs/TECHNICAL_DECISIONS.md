# Architecture and technical decisions

## Seven identifiable components

| Assignment component | Implementation | Hidden complexity | Production replacement |
| --- | --- | --- | --- |
| Voice interface | `app/main.py` Streamlit microphone, text fallback, result/state display, audio playback | Browser capture and reruns | Product web client with streaming media |
| Speech to text | `voice.py:transcribe_audio` | Multipart audio and provider timing | Streaming STT with noisy-audio adaptation |
| Understanding | One Agents SDK agent with typed tools | Intent choice, slot extraction, correction | Larger capacity model with the same schemas |
| Catalog and search | `search.py` plus MotherDuck | Parameterized filters, ranking, invariant checks | Search service with replicas and indexes |
| Response and TTS | `response.py` plus `voice.py` | Grounded composition, value validation, WAV batching | Streaming response and TTS gateway |
| Conversation state | Typed `ConversationState` plus SDK `SQLiteSession` | Slot merging and result references | Redis or durable session service |
| Evaluation and latency | `evals/evaluate_agent.py` and structured operation logs | Semantic checks and stage timing | CI evaluation service plus observability |

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
grounded search/detail results. A second model pass is reserved for follow-ups
that genuinely need reasoning over returned records.

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

1. Purchase defined-capacity provider tiers, add circuit breakers, and record
   per-provider tokens, rupee cost, availability, and p95 latency.
2. Stream STT and TTS and keep deterministic searches on the one-model-call
   path when no post-tool reasoning is required.
3. Replace local SQLite sessions with Redis or another concurrent state store;
   cap session lifetime and payload size.
4. Put catalog access behind a bounded connection pool/read service, add indexes
   for common filters, and cache low-cardinality catalog options.
5. Run the evaluation set in CI against a pinned model and maintain a separate
   canary set for provider/model changes.

No paid rupee-per-conversation figure is claimed because the submission uses
free-tier endpoints and did not collect provider billing. Production costing
would sum STT audio duration, input/output tokens, TTS characters, and database
requests from the existing per-stage logs.
