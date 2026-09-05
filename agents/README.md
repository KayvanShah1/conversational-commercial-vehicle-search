# Vehicle Search Agent

The package keeps the live path deliberately small:

1. `voice.py` transcribes audio and synthesizes the final response.
2. `agent.py` configures Vivi and registers the typed tools in `tools.py`.
3. `search.py` applies parameterized hard filters, ranks every matching row, and validates the returned records.
4. `response.py` creates spoken text only from catalog records.
5. `runner.py` retains cross-turn state and records stage timings.

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

Run the 27-turn live evaluation (the delay avoids free-tier bursts):

```powershell
uv run --package evals python -m evals.evaluate_agent --delay-seconds 10
```

The cases live in `evals/datasets/agent_cases.json`. Each run writes timestamped JSON
and Markdown reports under `data/evaluation/`.

Run the focused size, body, attribute, and follow-up evaluation:

```powershell
uv run --package evals python -m evals.evaluate_agent --cases evals/datasets/vehicle_variant_cases.json --delay-seconds 10
```

See the repository [setup guide](../docs/SETUP.md) and [evaluation report](../docs/EVALUATION.md) for configuration, output naming, and metric boundaries.
