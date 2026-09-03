# Setup guide

This guide takes Vivi from a fresh clone to the Streamlit voice-and-text demo. Commands are run from the repository root unless noted otherwise.

## Prerequisites

| Requirement | Why it is needed | Where to get it |
| --- | --- | --- |
| Git | Clone the repository | [git-scm.com](https://git-scm.com/downloads) |
| Python 3.13 | Project runtime | [python.org](https://www.python.org/downloads/) or let `uv` install it |
| `uv` | Workspace dependency and command runner | [Official installation guide](https://docs.astral.sh/uv/getting-started/installation/) |
| MotherDuck account and access token | Load and query the searchable catalog | [MotherDuck](https://app.motherduck.com/) → **Settings** → **Access tokens** |
| Groq account and API key | LLM, speech-to-text, and text-to-speech | [Groq API Keys](https://console.groq.com/keys) |
| OpenRouter API key | Optional cross-provider model fallback | [OpenRouter API Keys](https://openrouter.ai/settings/keys) |
| Microphone-enabled browser | Voice input and audio playback | A current Chrome, Edge, or Firefox release |

OpenRouter is optional. Text and voice operation require Groq; catalog loading and search require MotherDuck.

## 1. Install `uv`

On Windows, the simplest package-manager installation is:

```powershell
winget install --id=astral-sh.uv -e
```

For macOS, Linux, standalone installers, and alternative package managers, follow the [official `uv` installation guide](https://docs.astral.sh/uv/getting-started/installation/).

Confirm the installation:

```powershell
uv --version
```

## 2. Clone and install

```powershell
git clone https://github.com/KayvanShah1/conversational-commercial-vehicle-search.git
Set-Location conversational-commercial-vehicle-search
uv sync --all-packages --dev
```

`uv` reads `.python-version` and can install the required Python runtime when it is not already available.

## 3. Configure credentials

Create a local environment file:

```powershell
Copy-Item example.env .env
```

On macOS or Linux:

```bash
cp example.env .env
```

At minimum, replace these placeholders in `.env`:

```dotenv
MOTHERDUCK__TOKEN=<YOUR_MOTHERDUCK_TOKEN>
GROQ__API_KEYS=["<YOUR_PRIMARY_GROQ_KEY>"]
```

Multiple Groq keys can be supplied as a JSON list. The runtime rotates through configured keys and fallback models after retryable provider failures:

```dotenv
GROQ__API_KEYS=["<PRIMARY_KEY>","<SECONDARY_KEY>"]
```

Add OpenRouter only when its fallback routes are required:

```dotenv
OPENROUTER__API_KEY=<YOUR_OPENROUTER_KEY>
```

Never commit `.env` or paste real credentials into logs, screenshots, evaluation reports, or issues.

## Environment reference

### Required credentials

| Variable | Example | Purpose |
| --- | --- | --- |
| `MOTHERDUCK__TOKEN` | `<API_TOKEN>` | Authenticates catalog loading and agent queries |
| `GROQ__API_KEYS` | `["<API_KEY>"]` | Ordered JSON list used for model, STT, and TTS requests |

### MotherDuck and catalog generation

| Variable | Template value | Purpose |
| --- | ---: | --- |
| `MOTHERDUCK__DATABASE` | `vehicle_catalog` | Target database |
| `DATA_GENERATION__RECORD_COUNT` | `1000` | Number of generated listings |
| `DATA_GENERATION__SEED` | `42` | Reproducible random seed |
| `DATA_GENERATION__REPLACE` | `false` | Regenerate local catalog files before loading |
| `DATA_GENERATION__MIN_VEHICLE_AGE` | `1` | Youngest generated vehicle |
| `DATA_GENERATION__MAX_VEHICLE_AGE` | `12` | Oldest generated vehicle |
| `DATA_GENERATION__MIN_KM_PER_YEAR` | `8000` | Lower annual-distance bound |
| `DATA_GENERATION__MAX_KM_PER_YEAR` | `35000` | Upper annual-distance bound |
| `DATA_GENERATION__PAPERS_VERIFIED_PROBABILITY` | `0.82` | Synthetic document-verification probability |

### Groq models and speech

| Variable | Template value | Purpose |
| --- | --- | --- |
| `GROQ__BASE_URL` | `https://api.groq.com/openai/v1` | OpenAI-compatible Groq endpoint |
| `GROQ__PRIMARY_MODEL` | `openai/gpt-oss-120b` | First model route |
| `GROQ__FALLBACK_MODELS` | JSON list | Ordered Groq fallback models |
| `GROQ__STT_MODEL` | `whisper-large-v3-turbo` | Speech-to-text model |
| `GROQ__TTS_MODEL` | `canopylabs/orpheus-v1-english` | Text-to-speech model |
| `GROQ__TTS_VOICE` | `daniel` | Synthesized voice |
| `GROQ__TTS_FORMAT` | `wav` | Audio response format |
| `GROQ__TTS_MAX_CHARS` | `200` | Per-request TTS limit; longer responses are chunked and stitched |

### Optional OpenRouter fallback

| Variable | Template value | Purpose |
| --- | --- | --- |
| `OPENROUTER__API_KEY` | unset | Enables cross-provider fallbacks |
| `OPENROUTER__BASE_URL` | `https://openrouter.ai/api/v1` | OpenAI-compatible endpoint |
| `OPENROUTER__FALLBACK_MODELS` | JSON list | Ordered OpenRouter fallback models |

### Runtime and storage

| Variable | Template value | Purpose |
| --- | ---: | --- |
| `AGENT_RUNTIME__MAX_TURNS` | `6` | Maximum SDK turns per user request |
| `AGENT_RUNTIME__MODEL_TIMEOUT_SECONDS` | `8.0` | Timeout for each model route |
| `AGENT_RUNTIME__TOOL_TIMEOUT_SECONDS` | `15.0` | Catalog tool timeout |
| `AGENT_RUNTIME__TRACING_ENABLED` | `false` | Enables Agents SDK tracing |
| `AGENT_RUNTIME__TRACE_INCLUDE_SENSITIVE_DATA` | `false` | Controls sensitive trace content; keep disabled for normal use |
| `SESSION_DB_PATH` | `data/sessions/agent_sessions.sqlite` | Local conversation-history database |
| `RUN_MOTHERDUCK_INTEGRATION_TESTS` | `0` | Opt-in switch for the live database test |

The committed [`example.env`](../example.env) is the authoritative copy-ready template. Model availability and provider quotas can change; adjust model identifiers there rather than changing application code.

## 4. Prepare the catalog

The repository includes generated CSV and Parquet artifacts. Load the Parquet catalog into MotherDuck:

```powershell
uv run python -m vehicle_catalog_generator.load
```

The command generates local files when they are missing, then creates or replaces `vehicle_catalog.vehicles` in MotherDuck. Set `DATA_GENERATION__REPLACE=true` only when you intentionally want to regenerate the local artifacts before loading them.

Initial loading requires a token that can create or replace the table. After the catalog is prepared, the running agent can use a separate read-only token.

To generate the files without loading MotherDuck:

```powershell
uv run python -m vehicle_catalog_generator.generator
```

## 5. Run Vivi

```powershell
uv run --package app streamlit run app/main.py
```

Open <http://localhost:8501>. Allow microphone access when the browser asks. Text input remains available if microphone permission or a speech provider is unavailable.

For a terminal-only chat:

```powershell
uv run --package agents python analysis/agent_chat.py
```

## Verification

Run local static checks and unit tests:

```powershell
uv run ruff check agents app evals tests
uv run pytest -q
```

The live MotherDuck integration test is intentionally opt-in because it sends a real query to the configured database:

```powershell
$env:RUN_MOTHERDUCK_INTEGRATION_TESTS = "1"
uv run pytest tests/vehicle_search_agent/test_motherduck_read_only_integration.py -q
```

Evaluation is also provider-backed. Follow [the evaluation guide](EVALUATION.md) when a fresh live score is required.

## Troubleshooting

### Settings report an unconfigured key

Confirm that `.env` exists at the repository root, placeholder values were replaced, and `GROQ__API_KEYS` is valid JSON with double quotes.

### Every model route returns HTTP 429

The configured free-tier quota or shared model capacity is exhausted. Wait for the provider window to reset, configure another Groq key, enable the optional OpenRouter routes, or use a paid-capacity model. Vivi fails closed instead of inventing catalog results.

### MotherDuck authentication fails

Create a fresh access token from MotherDuck settings, confirm `MOTHERDUCK__DATABASE`, and rerun the catalog load. Keep the agent token read-only when the database has already been prepared.

### The microphone is unavailable

Use `localhost`, grant browser microphone permission, and confirm no other application has exclusive access to the device. The text composer exercises the same conversational path without STT or TTS.

### No audio plays

Check browser autoplay permissions and Groq TTS quota. The textual response remains the source of truth and is shown even when speech synthesis fails.
