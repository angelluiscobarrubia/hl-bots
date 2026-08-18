# Multi-stage production Dockerfile for the FastAPI backend.
#
# Stage 1 (builder): installs Poetry, exports/installs runtime dependencies.
# Stage 2 (runtime): copies only the installed packages + application code,
#                    runs uvicorn as a non-root user.
#
# Used by docker-compose (migrate + backend) and the CD pipeline.
#
# NOTE: pyproject.toml and poetry.lock live at the repo root, so the build
# context must be the repository root (`.`), not `./backend`. See the
# docker-compose `build.context` values and the CD workflow.

# ---------- Stage 1: builder ----------
FROM python:3.11-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_VERSION=1.8.3 \
    POETRY_HOME=/opt/poetry \
    POETRY_VIRTUALENVS_CREATE=false

# System deps needed to build wheels (cryptography, asyncpg, etc.)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install "poetry==${POETRY_VERSION}"

WORKDIR /build

# Copy only the manifests first so dependency layers are cached independently
# of source changes. (Manifests are at the repo root, which is the build context.)
COPY pyproject.toml poetry.lock* ./

# Install runtime dependencies only (no dev group, no root project).
# --no-root skips installing the project itself (package-mode=false anyway).
RUN poetry install --no-interaction --no-ansi --no-root --only main

# ---------- Stage 2: runtime ----------
FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Runtime system deps (much smaller than the builder set) + non-root user.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid 1000 --create-home appuser

WORKDIR /app

# Copy installed Python packages and console scripts from the builder stage.
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy the application source code (backend/ is the app root: src/, strategies/,
# alembic/, alembic.ini).
COPY backend/ .

# Run as a non-root user for security.
USER appuser

EXPOSE 8000

# Health check against the /health endpoint.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
