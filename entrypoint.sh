#!/bin/sh
set -e

echo "==> Running database migrations (alembic upgrade head)..."
uv run alembic upgrade head

if [ "$RUN_SEED" = "true" ]; then
    echo "==> Seeding database (database.seed)..."
    uv run python -m database.seed
fi

echo "==> Starting application process..."
exec "$@"
