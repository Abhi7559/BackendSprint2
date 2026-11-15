"""
pre_deployment/check_secrets.py

Standalone Secrets Manager pre-deployment check.
Validates:
1. Floci / Secrets Manager endpoint is reachable.
2. Required secret exists.
3. SecretString payload contains valid JSON.
4. Required fields (DATABASE_PASSWORD, JWT_SECRET_KEY) exist and are non-empty.

Uses the single core.secrets module (no duplicate boto3 logic).
Never prints or logs sensitive credential values.
"""
import os
import sys
from pathlib import Path

# Add project root to sys.path so core can be imported
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from core.secrets import SecretsManagerError, get_secrets


def check_secrets() -> None:
    secret_id = os.getenv("AWS_SECRET_ID", "film-review/platform")
    endpoint = os.getenv("AWS_SECRETS_ENDPOINT_URL", "http://localhost:4566")

    print(f"--> [Pre-Deployment] Checking AWS Secrets Manager at: {endpoint}")
    print(f"--> [Pre-Deployment] Verifying required secret: '{secret_id}'")

    try:
        secrets = get_secrets(force_refresh=True)
        # Verify non-empty
        if not secrets.DATABASE_PASSWORD or not secrets.JWT_SECRET_KEY:
            raise SecretsManagerError(f"Secret '{secret_id}' contains empty values.")

        print(f"[SUCCESS] Secret '{secret_id}' retrieved, parsed, and validated successfully.")
    except SecretsManagerError as err:
        print(f"[FATAL] Secrets Manager check failed: {err}", file=sys.stderr)
        sys.exit(1)
    except Exception as err:
        print(f"[FATAL] Unexpected error during Secrets Manager check for '{secret_id}': {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    check_secrets()
