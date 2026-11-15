"""
core/secrets.py

Dedicated module for retrieving, validating, and caching application secrets
from AWS Secrets Manager (or local Floci simulator).

Responsibilities:
- Sole owner of boto3 Secrets Manager client access.
- Validates required fields: DATABASE_PASSWORD, JWT_SECRET_KEY.
- Handles ClientError (ResourceNotFoundException, AccessDeniedException, Endpoint failures).
- Caches the validated credentials in memory for the process lifetime.
- Never logs or prints sensitive secret values.
"""
from dataclasses import dataclass
import json
import logging
import os
import sys
from typing import Optional

import boto3
from botocore.exceptions import ClientError, EndpointConnectionError

logger = logging.getLogger(__name__)


class SecretsManagerError(Exception):
    """Base exception for all Secrets Manager retrieval errors."""
    pass


@dataclass(frozen=True)
class AppSecrets:
    """Typed, validated immutable container for application secrets."""
    DATABASE_PASSWORD: str
    JWT_SECRET_KEY: str
    THIRD_PARTY_API_KEY: Optional[str] = None


# Process-lifetime in-memory cache
_CACHED_SECRETS: Optional[AppSecrets] = None


def get_secrets(force_refresh: bool = False) -> AppSecrets:
    """
    Retrieve application secrets from AWS Secrets Manager / Floci.
    Returns cached secrets on subsequent calls unless force_refresh=True.
    Raises SecretsManagerError with clear message identifying the failed secret name.
    """
    global _CACHED_SECRETS

    if _CACHED_SECRETS is not None and not force_refresh:
        return _CACHED_SECRETS

    secret_name = os.getenv("AWS_SECRET_ID", "film-review/platform")
    endpoint_url = os.getenv("AWS_SECRETS_ENDPOINT_URL", "http://localhost:4566")
    region_name = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    aws_access_key = os.getenv("AWS_ACCESS_KEY_ID", "test")
    aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY", "test")

    try:
        session = boto3.session.Session()
        client = session.client(
            service_name="secretsmanager",
            region_name=region_name,
            endpoint_url=endpoint_url,
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
        )

        response = client.get_secret_value(SecretId=secret_name)
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        if error_code == "ResourceNotFoundException":
            msg = f"Secret '{secret_name}' was not found in Secrets Manager."
        elif error_code in ("AccessDeniedException", "AccessDenied"):
            msg = f"Access denied while retrieving secret '{secret_name}' from Secrets Manager."
        else:
            msg = f"AWS Secrets Manager error [{error_code}] while retrieving secret '{secret_name}': {e}"
        logger.error(msg)
        raise SecretsManagerError(msg) from e
    except EndpointConnectionError as e:
        msg = f"Unable to connect to Secrets Manager endpoint at '{endpoint_url}' while retrieving '{secret_name}'."
        logger.error(msg)
        raise SecretsManagerError(msg) from e
    except Exception as e:
        msg = f"Unexpected error while retrieving secret '{secret_name}': {e}"
        logger.error(msg)
        raise SecretsManagerError(msg) from e

    # Parse and validate JSON payload
    secret_string = response.get("SecretString")
    if not secret_string:
        msg = f"Secret '{secret_name}' has no SecretString payload."
        logger.error(msg)
        raise SecretsManagerError(msg)

    try:
        data = json.loads(secret_string)
    except json.JSONDecodeError as e:
        msg = f"Secret '{secret_name}' contains invalid JSON: {e}"
        logger.error(msg)
        raise SecretsManagerError(msg) from e

    if not isinstance(data, dict):
        msg = f"Secret '{secret_name}' must be a JSON object (key-value dictionary)."
        logger.error(msg)
        raise SecretsManagerError(msg)

    # Validate required fields
    db_password = data.get("DATABASE_PASSWORD")
    jwt_secret = data.get("JWT_SECRET_KEY")
    third_party_key = data.get("THIRD_PARTY_API_KEY")

    missing_fields = []
    if not db_password or not str(db_password).strip():
        missing_fields.append("DATABASE_PASSWORD")
    if not jwt_secret or not str(jwt_secret).strip():
        missing_fields.append("JWT_SECRET_KEY")

    if missing_fields:
        fields_str = ", ".join(missing_fields)
        msg = f"Secret '{secret_name}' is missing required non-empty field(s): {fields_str}"
        logger.error(msg)
        raise SecretsManagerError(msg)

    _CACHED_SECRETS = AppSecrets(
        DATABASE_PASSWORD=str(db_password).strip(),
        JWT_SECRET_KEY=str(jwt_secret).strip(),
        THIRD_PARTY_API_KEY=str(third_party_key).strip() if third_party_key else None,
    )

    logger.info(f"Successfully loaded and cached application secrets from '{secret_name}'")
    return _CACHED_SECRETS


def reset_secrets_cache() -> None:
    """Helper for testing to reset the process-level in-memory cache."""
    global _CACHED_SECRETS
    _CACHED_SECRETS = None

