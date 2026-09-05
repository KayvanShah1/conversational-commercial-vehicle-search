# syntax=docker/dockerfile:1

FROM python:3.13-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11.23 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# Copy workspace manifests first so dependency installation remains cacheable.
COPY pyproject.toml uv.lock ./
COPY agents/pyproject.toml ./agents/
COPY app/pyproject.toml ./app/
COPY evals/pyproject.toml ./evals/
COPY utils/pyproject.toml ./utils/
COPY vehicle-catalog-generator/pyproject.toml ./vehicle-catalog-generator/

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --package app --no-dev --no-install-workspace

# Only the web app and its workspace dependencies are required at runtime.
COPY agents ./agents
COPY app ./app
COPY utils ./utils

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --package app --no-dev --no-editable


FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:${PATH}" \
    PORT=10000 \
    PROJECT_ROOT=/app \
    DATA_DIR=/app/data \
    LOG_DIR=/app/logs \
    SESSION_DATA_PATH=/app/data/sessions \
    SESSION_DB_PATH=/app/data/sessions/agent_sessions.sqlite

WORKDIR /app

RUN groupadd --system app \
    && useradd --system --gid app --create-home app \
    && mkdir -p /app/data/sessions /app/logs \
    && chown -R app:app /app

COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=builder --chown=app:app /app/app /app/app

USER app

EXPOSE 10000

HEALTHCHECK \
    --interval=30s \
    --timeout=5s \
    --start-period=30s \
    --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '10000') + '/_stcore/health', timeout=4)"

CMD ["sh", "-c", "exec streamlit run app/main.py --server.address=0.0.0.0 --server.port=${PORT:-10000} --server.headless=true --server.fileWatcherType=none --browser.gatherUsageStats=false"]
