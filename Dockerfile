# ─── Build stage ──────────────────────────────────────────────────────────────
FROM python:3.11-slim-bookworm AS builder

RUN apt-get update && apt-get upgrade -y && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir poetry==1.8.3
ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

WORKDIR /app
COPY pyproject.toml ./
RUN poetry install --without dev --no-root --no-lock && rm -rf $POETRY_CACHE_DIR

# ─── Runtime stage ────────────────────────────────────────────────────────────
FROM python:3.11-slim-bookworm AS runtime

RUN apt-get update && apt-get upgrade -y && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PORT=8000

COPY --from=builder /app/.venv .venv

# Application code
COPY main.py .
COPY agents/ agents/
COPY utils/ utils/

# Database — Python modules + SQLite file (olist.db)
COPY database/ database/

EXPOSE 8000

# Shell form agar $PORT dari Cloud Run terbaca secara dinamis
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
