# ─────────────────────────────────────────────────────────────────────────────
# AI Code Review Crew — Multi-stage Dockerfile
# Stage 1 (builder): installs Poetry + all Python deps into a venv
# Stage 2 (runtime): copies only the venv + app code — no build tools
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1: Builder ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

# Build-time deps needed to compile cryptography, pymysql wheels, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libssl-dev \
    libffi-dev \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry — pinned version for reproducibility
# POETRY_VIRTUALENVS_IN_PROJECT=true creates .venv inside /app
# so the runtime stage can copy it via a single COPY --from=builder
ENV POETRY_VERSION=1.8.3
ENV POETRY_HOME=/opt/poetry
ENV POETRY_VIRTUALENVS_IN_PROJECT=true
ENV POETRY_NO_INTERACTION=1

RUN curl -sSL https://install.python-poetry.org | python3 -

ENV PATH="$POETRY_HOME/bin:$PATH"

WORKDIR /app

# Copy dependency files first so Docker caches this layer.
# Deps only reinstall when pyproject.toml or poetry.lock change.
COPY pyproject.toml poetry.lock* ./

# Install main deps only — no pytest/ruff/mypy in the final image
RUN poetry install --only main --no-root --no-ansi

# Copy full source then install the project package itself
COPY . .
RUN poetry install --only main --no-ansi


# ── Stage 2: Runtime ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Minimal runtime system deps:
#   libmagic1 — file type detection used by LlamaIndex SimpleDirectoryReader
#   git       — required by GitPython for diff parsing
#   curl      — used by healthcheck probes and fetch_kb.sh
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Non-root user — never run app code as root inside a container
RUN groupadd --gid 1001 crew \
    && useradd --uid 1001 --gid crew --shell /bin/bash --create-home crew

WORKDIR /app

# Copy the virtualenv built in stage 1
COPY --from=builder /app/.venv /app/.venv

# Copy application source with correct ownership
COPY --chown=crew:crew . .

# Create runtime directories (also mounted as volumes in docker-compose)
RUN mkdir -p /app/reports /app/credentials /app/knowledge_base \
    && chown -R crew:crew /app

# Activate the venv — no inline comments on ENV lines (Docker syntax restriction)
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app

USER crew

# Smoke-test: verify key packages import cleanly at build time
RUN python -c "import crewai; import llama_index.core; import qdrant_client; print('imports ok')"

# Default command — overridden in docker-compose or docker run
CMD ["python", "main.py", "--help"]