# syntax=docker/dockerfile:1.6
#
# Multi-stage build:
#   Stage 1 (builder): compile wheels for deps that need building (psycopg, lxml, etc.)
#   Stage 2 (runtime): slim image with just the compiled wheels + app code
#
# Final image is ~180MB, runs as non-root, starts in <2s.

# ─── STAGE 1: builder ────────────────────────────────────────────
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Build-time system deps for compiling wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

COPY requirements.txt .

# Build wheels for all dependencies
RUN pip wheel --no-deps --wheel-dir /wheels -r requirements.txt


# ─── STAGE 2: runtime ────────────────────────────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Runtime-only system deps (libpq for psycopg, curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Non-root user for security
RUN groupadd --system --gid 1000 app \
    && useradd --system --uid 1000 --gid app --create-home --shell /bin/bash app

WORKDIR /app

# Install deps from pre-built wheels
COPY --from=builder /wheels /wheels
COPY requirements.txt .
RUN pip install --no-index --find-links=/wheels -r requirements.txt \
    && rm -rf /wheels

# Copy app source
COPY --chown=app:app . .

USER app

EXPOSE 8000

# Healthcheck hits the /health endpoint (add one to your FastAPI app if missing)
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Gunicorn with uvicorn workers. 2 workers is safe for a 2GB droplet; tune later.
# --access-logfile - pipes access logs to stdout so Docker captures them.
CMD ["gunicorn", "app.main:app", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "2", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--timeout", "60"]