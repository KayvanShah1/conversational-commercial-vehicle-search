# Agent code-quality and logic review

Date: 2026-09-03

## Conclusion

The submitted agent is a bounded single-agent system, not an agent hierarchy.
Its separation is by real responsibility: model/tool routing, typed data,
catalog access, grounded response construction, session orchestration, and
voice I/O. Removing those seams would combine unrelated failure modes rather
than make the code easier to explain.

The implementation still has domain rules, but they are deliberately narrow:
they protect hard constraints and conversational references that varied across
small/free models. The 294-word prompt describes tool choice and safety; it does
not enumerate truck models or hard-code expected evaluation answers.

## Findings and actions

| Review concern | Finding | Action/status |
| --- | --- | --- |
| Redundant API-key checks | Groq keys were checked independently in `agent.py` and `voice.py` | Removed. Pydantic validates and deduplicates one `GROQ__API_KEYS` list; OpenRouter remains normalized and optional. |
| Unused logging utility | The current primitive is used by generation, loading, LLM, search, STT, TTS, and full turns | Kept `OperationLogContext`; no second timer wrapper exists. |
| Tool-selector agent | A second agent would duplicate a three-choice routing decision | Not added. The system prompt names when each typed tool applies. |
| Service/repository wrappers | Search has one concrete MotherDuck consumer | No service layer or repository interface was added. Search functions own their queries directly. |
| Database lifecycle | A process-global connection would be shared unsafely across Streamlit sessions | One read-only connection is opened per catalog operation, reused for that operation, and closed by the shared context manager. |
| Prompt duplication | Routing appears in the prompt and accepted values appear in schemas/docstrings | Kept only this intentional split: prompt says *when*; schemas say *what is valid*. |
| Literal safeguard helpers | `_mentioned` and `_explicit` are tiny, but protect explicit fuel/body/category constraints from model drift | Kept. Inlining them three times would be longer and less clear. |
| TTS chunking | Orpheus accepts at most 200 characters per request | Kept `_text_chunks` and `_stitch_wav`; they are provider-bound behavior with focused tests, not generic abstraction. |
| Fallback wrapper | The SDK model interface accepts one model while the demo needs key and cross-provider failover | Kept the small adapter. It walks the finite model/key routes only on retryable failures and resets per user turn. |
| Grounded response structures | `GroundedResponse` carries fallback text and validation checks | Kept. This is the code-level anti-hallucination boundary required by the assignment. |
| Deterministic result duplication | SQL filters are checked again against returned records | Kept intentionally. The second check detects a violated hard-filter invariant. |

## Logic boundaries

- The model chooses an intent and typed arguments; it never writes SQL.
- `search_vehicles` applies a slot patch and never silently clears omitted
  constraints.
- `get_vehicle_details` resolves singular/plural references against current
  result IDs and performs one bounded lookup for all requested records.
- Search returns at most three ranked vehicles and verifies each record against
  every active hard filter.
- A natural post-tool reply is accepted only when required facts remain in
  order and every number comes from the grounded facts. Otherwise the
  deterministic fallback is returned.
- Invalid tool arguments are returned to the model for repair; after three
  failures the turn ends with a rephrase request.
- General commercial-vehicle guidance can use no tool, but numeric vehicle
  claims are rejected unless grounded in catalog results.

## Complexity that remains on purpose

The largest agent files are `tools.py`, `search.py`, and `response.py`. Splitting
them further into one-use classes would add indirection without reducing logic.
Their current boundaries correspond directly to the live explanation: decide
and validate tool input, query/rank records, then compose/validate output.

The free-model fallback list is operational complexity, not domain logic. It is
visible in settings because free-tier quotas are the dominant live-demo risk.
Production would replace it with defined-capacity routing and circuit-breaker
telemetry, not more prompt rules.

## Avoided overengineering

- No intent agent, slot agent, selector agent, critic agent, or orchestration graph
- No generated SQL, raw database tool, generic database service, or repository interface
- No global connection passed through agent state
- No hand-written parser intended to replace natural-language understanding
- No canned expected answer matching in the agent
- No framework-specific UI layer around `VehicleSearchSession`

## Verification result

1. Ruff passed over source, app, evals, and tests.
2. The full unit suite passed: 83 passed and 1 opt-in integration test skipped.
3. Both live datasets passed (23 core + 18 focused cases), and the committed
   catalog contains 1,000 rows.
4. Streamlit AppTest rendered the native text-and-microphone composer, sidebar,
   results, and empty states without a framework exception. Browser screenshot
   QA could not be repeated because the browser-control connection timed out.
5. Live STT and TTS passed. A four-turn text smoke passed greeting, heavy-
   machinery search, plural weight lookup, and unsafe data-access refusal.
6. Key and model rotation recovered from intermittent rate limits during both
   complete live evaluation runs.
