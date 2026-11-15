#!/bin/sh
# Exit immediately if any command fails
set -e

echo "=========================================================="
echo "==> [Safety Gate] Starting Pre-Deployment Verification"
echo "=========================================================="

# 1. Run environment and infrastructure connectivity checks
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
sh "$SCRIPT_DIR/pre_deployment.sh"

# 2. Run unit and integration test suite
echo "=========================================================="
echo "==> [Safety Gate] Running Test Suite Before Server Start"
echo "=========================================================="
if ! pytest tests; then
    echo "----------------------------------------------------------" >&2
    echo "[FATAL] Test suite failed! Application startup aborted." >&2
    echo "----------------------------------------------------------" >&2
    exit 1
fi
echo "[SUCCESS] All tests passed."

# 3. Run database migrations if alembic configuration is present
if [ -f "alembic.ini" ]; then
    echo "=========================================================="
    echo "==> Applying Database Migrations (alembic upgrade head)..."
    echo "=========================================================="
    alembic upgrade head
fi

# 4. Optional seed step
if [ "$RUN_SEED" = "true" ]; then
    echo "=========================================================="
    echo "==> Running Database Seed..."
    echo "=========================================================="
    python -m database.seed
fi

# 5. Start uvicorn server (or command passed as arguments if any)
echo "=========================================================="
echo "==> [Safety Gate Passed] Starting Uvicorn Server"
echo "=========================================================="
if [ $# -gt 0 ]; then
    exec "$@"
else
    exec uvicorn main:app --host 0.0.0.0 --port 8000
fi
