# Vehicle Search Agent

The package is organized by capability. Each package exposes its stable public
API from `__init__.py`, while implementation files stay focused:

1. `agent/` defines Vivi, its prompt, provider routes, and tool registration.
2. `models/` owns catalog, filter, enum, state, and turn schemas.
3. `search/` separates parameterized queries, deterministic ranking, and search orchestration.
4. `tools/` contains one module per model-facing operation plus shared turn context.
5. `response/` renders catalog fields and comparisons, composes responses, and validates grounding.
6. `runner/` owns conversation sessions and telemetry/cost measurement.
7. `voice/` separates provider key rotation, transcription, and WAV synthesis.

`settings.py` remains at the package root because every runtime capability
consumes the same validated configuration.

The model never writes SQL. Search and detail tools build the factual response
from catalog records. Vivi may rephrase the surrounding language, but code
checks that the vehicle facts remain in order and that no new number appears;
otherwise it uses the grounded fallback.

Run the text smoke test from the workspace root:

```powershell
uv run --package agents python analysis/agent_smoke_test.py
```

For an interactive typed conversation:

```powershell
uv run --package agents python analysis/agent_chat.py
```

Text and voice share the same `VehicleSearchSession` and conversation state.
Voice adds transcription before the text turn, then splits long responses into
Groq's 200-character TTS requests and stitches the returned WAV audio.

`GROQ__API_KEYS` is a JSON list. Model calls try every configured key for Groq's
120B model before moving to Groq 20B, Qwen 3.6 27B, and Qwen 3.8 27B. Agent
requests keep the last successful route as the next request's starting point.
STT and TTS independently remember the last successful key for their model.
Retryable model failures and speech HTTP 429 responses rotate through the
configured routes once; the route list itself is the retry bound.

Run the focused tests:

```powershell
uv run pytest tests/vehicle_search_agent -q
```

Run the 28-turn live evaluation (the delay avoids free-tier bursts):

```powershell
uv run --package evals python -m evals.evaluator.agent --delay-seconds 10
```

The cases live in `evals/datasets/agent_cases.json`. Each run writes timestamped JSON
and Markdown reports under `data/evaluation/`.

Run the focused size, body, attribute, and follow-up evaluation:

```powershell
uv run --package evals python -m evals.evaluator.agent --cases evals/datasets/vehicle_variant_cases.json --delay-seconds 10
```

See the repository [setup guide](../docs/SETUP.md) and [evaluation report](../docs/EVALUATION.md) for configuration, output naming, and metric boundaries.
