# Use an official lightweight Python image
FROM python:3.12-slim

# Set working directory inside container
WORKDIR /app

# Prevent Python from writing .pyc files and enable unbuffered output for logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# Install uv from official ghcr image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependency configuration and lockfile
COPY pyproject.toml uv.lock ./

# Install dependencies using uv sync (frozen ensures exact lockfile versions)
RUN uv sync --frozen --no-install-project

# Copy application source code
COPY . .

# Ensure entrypoint script has executable permissions
RUN chmod +x /app/entrypoint.sh

# Install the application itself
RUN uv sync --frozen

# Expose FastAPI / Uvicorn default port
EXPOSE 8000

# Entrypoint manages database migrations and conditional seeding
ENTRYPOINT ["/app/entrypoint.sh"]

# Default command executed by entrypoint's exec "$@"
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
