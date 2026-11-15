# ==============================================================================
# Multi-stage Dockerfile for FastAPI Application using uv
# Stage 1 (builder): Installs production dependencies into a virtual environment
# Stage 2 (runner):  Minimal runtime image serving the app with no build tools
# ==============================================================================

# ------------------------------------------------------------------------------
# 1. Builder Stage
# ------------------------------------------------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

# Install uv from official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependency specifications first to leverage Docker layer caching
COPY pyproject.toml uv.lock ./

# Install all dependencies including dev (so pytest is available for the pre-deployment test suite)
RUN uv sync --frozen --no-install-project

# Copy application source code for editable/project install
COPY . .

# Install application package into .venv with dev dependencies (pytest, pytest-asyncio, etc.)
RUN uv sync --frozen

# ------------------------------------------------------------------------------
# 2. Runner Stage (Minimal Runtime Image)
# ------------------------------------------------------------------------------
FROM python:3.12-slim AS runner

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# Copy uv binary so entrypoint can run uv commands (alembic, python) if needed
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/

# Copy the prepared virtual environment from the builder stage
COPY --from=builder /app/.venv /app/.venv

# Copy only the application source code and runtime assets required to run the service
COPY alembic /app/alembic
COPY alembic.ini /app/alembic.ini
COPY core /app/core
COPY dao /app/dao
COPY database /app/database
COPY dependencies /app/dependencies
COPY exceptions /app/exceptions
COPY handlers /app/handlers
COPY models /app/models
COPY routes /app/routes
COPY schemas /app/schemas
COPY services /app/services
COPY templates /app/templates
COPY tests /app/tests
COPY pre_deployment /app/pre_deployment
COPY main.py /app/main.py
COPY pyproject.toml /app/pyproject.toml
COPY uv.lock /app/uv.lock
COPY pre_deployment.sh /app/pre_deployment.sh
COPY startup.sh /app/startup.sh

# Ensure scripts are executable
RUN chmod +x /app/pre_deployment.sh /app/startup.sh

# Expose FastAPI / Uvicorn port
EXPOSE 8000

# Safety gate is executed on every container start via CMD (can also be paired with ENTRYPOINT)
CMD ["/app/startup.sh"]
