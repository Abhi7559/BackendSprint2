#!/bin/sh
# Exit immediately if a command exits with a non-zero status
set -e

echo "=========================================================="
echo "==> [Pre-Deployment Gate] Step 1: Environment Variables"
echo "=========================================================="

# List of all mandatory environment variables
REQUIRED_VARS="
DATABASE_URL
TOKEN_SECRET_KEY
TOKEN_ACCESS_TOKEN_EXPIRE_MINUTES
TOKEN_REFRESH_TOKEN_EXPIRE_DAYS
API_VERSION
REDIS_URL
"

MISSING_VARS=""
HAS_MISSING=0

for var_name in $REQUIRED_VARS; do
    # Check if variable is unset or empty
    eval val=\$$var_name
    if [ -z "$val" ]; then
        echo "[ERROR] Missing required environment variable: $var_name" >&2
        MISSING_VARS="$MISSING_VARS $var_name"
        HAS_MISSING=1
    fi
done

if [ "$HAS_MISSING" -eq 1 ]; then
    echo "----------------------------------------------------------" >&2
    echo "[FATAL] Pre-deployment checks failed! Missing variables:$MISSING_VARS" >&2
    echo "Refusing to start application in an unconfigured state." >&2
    echo "----------------------------------------------------------" >&2
    exit 1
fi

echo "[SUCCESS] All required environment variables are present."

echo "=========================================================="
echo "==> [Pre-Deployment Gate] Step 2: Database Connectivity"
echo "=========================================================="
python pre_deployment/check_db.py

echo "=========================================================="
echo "==> [Pre-Deployment Gate] Step 3: Redis Connectivity"
echo "=========================================================="
python pre_deployment/check_redis.py

echo "=========================================================="
echo "==> [Pre-Deployment Gate] All pre-deployment checks passed!"
echo "=========================================================="
