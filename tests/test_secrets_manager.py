"""
tests/test_secrets_manager.py

Comprehensive unit tests for core.secrets and Secrets Manager integration.
All tests use pytest and mock boto3 responses - zero contact with real AWS or Floci required.

Tests cover:
1. Successful secret retrieval.
2. JSON parsing.
3. Correct typed values.
4. Secret caching: repeated calls do not retrieve again.
5. ResourceNotFoundException.
6. AccessDeniedException.
7. Endpoint unreachable (EndpointConnectionError).
8. Invalid JSON.
9. Missing required secret field (DATABASE_PASSWORD, JWT_SECRET_KEY).
10. Startup fails when secret retrieval fails.
11. Existing central config interface still works (DATABASE_URL, TOKEN_SECRET_KEY).
12. Pre-deployment gate fails when a required secret is unavailable.
13. Pre-deployment gate passes when all dependencies and secrets are available.
"""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from botocore.exceptions import ClientError, EndpointConnectionError

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from core.secrets import AppSecrets, SecretsManagerError, get_secrets, reset_secrets_cache
from core.config import Settings


@pytest.fixture(autouse=True)
def clean_cache():
    """Ensure in-memory secrets cache is wiped before and after each test."""
    reset_secrets_cache()
    yield
    reset_secrets_cache()


# ---------------------------------------------------------------------------
# 1. Successful Retrieval, Parsing, and Typing
# ---------------------------------------------------------------------------

def test_successful_secret_retrieval_and_parsing():
    """1, 2, 3: Verifies successful retrieval, JSON parsing, and typed container."""
    secret_payload = {
        "DATABASE_PASSWORD": "super_secret_db_pass",
        "JWT_SECRET_KEY": "super_secret_jwt_key_123",
        "THIRD_PARTY_API_KEY": "tmdb_api_key_456",
    }

    mock_client = MagicMock()
    mock_client.get_secret_value.return_value = {
        "SecretString": json.dumps(secret_payload)
    }

    with patch("boto3.session.Session.client", return_value=mock_client):
        secrets = get_secrets(force_refresh=True)

        assert isinstance(secrets, AppSecrets)
        assert secrets.DATABASE_PASSWORD == "super_secret_db_pass"
        assert secrets.JWT_SECRET_KEY == "super_secret_jwt_key_123"
        assert secrets.THIRD_PARTY_API_KEY == "tmdb_api_key_456"
        assert mock_client.get_secret_value.call_count == 1


# ---------------------------------------------------------------------------
# 4. Secret In-Memory Caching
# ---------------------------------------------------------------------------

def test_secret_caching_repeated_calls_do_not_retrieve_again():
    """4: Confirms get_secrets() caches in memory and makes only 1 boto3 call."""
    reset_secrets_cache()
    secret_payload = {
        "DATABASE_PASSWORD": "cached_password",
        "JWT_SECRET_KEY": "cached_jwt_key",
    }

    mock_client = MagicMock()
    mock_client.get_secret_value.return_value = {
        "SecretString": json.dumps(secret_payload)
    }

    with patch("boto3.session.Session.client", return_value=mock_client):
        call1 = get_secrets()
        call2 = get_secrets()
        call3 = get_secrets()

        assert call1 == call2 == call3
        # boto3 client was only called once!
        assert mock_client.get_secret_value.call_count == 1


# ---------------------------------------------------------------------------
# 5. ResourceNotFoundException
# ---------------------------------------------------------------------------

def test_resource_not_found_exception():
    """5: Identifies secret name when secret does not exist."""
    mock_client = MagicMock()
    error_response = {"Error": {"Code": "ResourceNotFoundException", "Message": "Secret not found"}}
    mock_client.get_secret_value.side_effect = ClientError(error_response, "GetSecretValue")

    with patch("boto3.session.Session.client", return_value=mock_client):
        with pytest.raises(SecretsManagerError) as exc_info:
            get_secrets(force_refresh=True)

        assert "was not found" in str(exc_info.value)
        assert "film-review/platform" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 6. AccessDeniedException
# ---------------------------------------------------------------------------

def test_access_denied_exception():
    """6: Identifies secret name on access denial."""
    mock_client = MagicMock()
    error_response = {"Error": {"Code": "AccessDeniedException", "Message": "User not authorized"}}
    mock_client.get_secret_value.side_effect = ClientError(error_response, "GetSecretValue")

    with patch("boto3.session.Session.client", return_value=mock_client):
        with pytest.raises(SecretsManagerError) as exc_info:
            get_secrets(force_refresh=True)

        assert "Access denied" in str(exc_info.value)
        assert "film-review/platform" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 7. Endpoint Unreachable
# ---------------------------------------------------------------------------

def test_endpoint_connection_error():
    """7: Identifies endpoint and secret when Floci / simulator is offline."""
    mock_client = MagicMock()
    mock_client.get_secret_value.side_effect = EndpointConnectionError(endpoint_url="http://localhost:4566")

    with patch("boto3.session.Session.client", return_value=mock_client):
        with pytest.raises(SecretsManagerError) as exc_info:
            get_secrets(force_refresh=True)

        assert "Unable to connect to Secrets Manager endpoint" in str(exc_info.value)
        assert "http://localhost:4566" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 8. Invalid JSON
# ---------------------------------------------------------------------------

def test_invalid_json_payload():
    """8: Detects malformed JSON payload."""
    mock_client = MagicMock()
    mock_client.get_secret_value.return_value = {
        "SecretString": "not_valid_json{{{{}}"
    }

    with patch("boto3.session.Session.client", return_value=mock_client):
        with pytest.raises(SecretsManagerError) as exc_info:
            get_secrets(force_refresh=True)

        assert "contains invalid JSON" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 9. Missing Required Secret Field
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("missing_payload, missing_name", [
    ({"JWT_SECRET_KEY": "valid_key"}, "DATABASE_PASSWORD"),
    ({"DATABASE_PASSWORD": "valid_password"}, "JWT_SECRET_KEY"),
    ({"DATABASE_PASSWORD": "  ", "JWT_SECRET_KEY": "valid_key"}, "DATABASE_PASSWORD"),
])
def test_missing_or_empty_required_field(missing_payload, missing_name):
    """9: Rejects payload missing DATABASE_PASSWORD or JWT_SECRET_KEY."""
    mock_client = MagicMock()
    mock_client.get_secret_value.return_value = {
        "SecretString": json.dumps(missing_payload)
    }

    with patch("boto3.session.Session.client", return_value=mock_client):
        with pytest.raises(SecretsManagerError) as exc_info:
            get_secrets(force_refresh=True)

        assert "missing required non-empty field(s)" in str(exc_info.value)
        assert missing_name in str(exc_info.value)


# ---------------------------------------------------------------------------
# 10. Startup Fails when Secret Retrieval Fails
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fastapi_lifespan_startup_fails_on_secret_error():
    """10: Verifies lifespan aborts application startup if secrets cannot be fetched."""
    from main import lifespan

    app = MagicMock()
    with patch("main.get_secrets", side_effect=SecretsManagerError("Simulated Secret Failure")):
        with pytest.raises(SystemExit):
            async with lifespan(app):
                pass


# ---------------------------------------------------------------------------
# 11. Central Config Interface Works Unmodified
# ---------------------------------------------------------------------------

def test_central_config_interface_remains_intact():
    """11: Verifies settings.DATABASE_URL and settings.TOKEN_SECRET_KEY are populated from secrets."""
    mock_secrets = AppSecrets(
        DATABASE_PASSWORD="retrieved_password",
        JWT_SECRET_KEY="retrieved_token_key",
    )

    with patch("core.config.get_secrets", return_value=mock_secrets):
        cfg = Settings(
            DB_USER="custom_user",
            DB_HOST="custom_host",
            DB_PORT=5433,
            DB_NAME="custom_db",
        )

        assert cfg.DATABASE_URL == "postgresql+asyncpg://custom_user:retrieved_password@custom_host:5433/custom_db"
        assert cfg.TOKEN_SECRET_KEY == "retrieved_token_key"


# ---------------------------------------------------------------------------
# 12 & 13. Pre-Deployment Gate Check Functionality
# ---------------------------------------------------------------------------

def test_pre_deployment_check_secrets_fails_on_error():
    """12: Pre-deployment check_secrets exits with code 1 on secret failure."""
    from pre_deployment.check_secrets import check_secrets

    with patch("pre_deployment.check_secrets.get_secrets", side_effect=SecretsManagerError("Secret missing")):
        with pytest.raises(SystemExit) as exc_info:
            check_secrets()

        assert exc_info.value.code == 1


def test_pre_deployment_check_secrets_succeeds_when_available():
    """13: Pre-deployment check_secrets passes cleanly when secret is valid."""
    from pre_deployment.check_secrets import check_secrets

    mock_secrets = AppSecrets(
        DATABASE_PASSWORD="valid_pass",
        JWT_SECRET_KEY="valid_token",
    )

    with patch("pre_deployment.check_secrets.get_secrets", return_value=mock_secrets):
        # Must execute cleanly without raising SystemExit(1)
        check_secrets()


if __name__ == "__main__":
    import asyncio
    print("Running test_successful_secret_retrieval_and_parsing...")
    test_successful_secret_retrieval_and_parsing()
    print("Running test_secret_caching_repeated_calls_do_not_retrieve_again...")
    test_secret_caching_repeated_calls_do_not_retrieve_again()
    print("Running test_resource_not_found_exception...")
    test_resource_not_found_exception()
    print("Running test_access_denied_exception...")
    test_access_denied_exception()
    print("Running test_endpoint_connection_error...")
    test_endpoint_connection_error()
    print("Running test_invalid_json_payload...")
    test_invalid_json_payload()
    print("Running test_missing_or_empty_required_field...")
    test_missing_or_empty_required_field({"JWT_SECRET_KEY": "valid_key"}, "DATABASE_PASSWORD")
    test_missing_or_empty_required_field({"DATABASE_PASSWORD": "valid_password"}, "JWT_SECRET_KEY")
    test_missing_or_empty_required_field({"DATABASE_PASSWORD": "  ", "JWT_SECRET_KEY": "valid_key"}, "DATABASE_PASSWORD")
    print("Running test_fastapi_lifespan_startup_fails_on_secret_error...")
    asyncio.run(test_fastapi_lifespan_startup_fails_on_secret_error())
    print("Running test_central_config_interface_remains_intact...")
    test_central_config_interface_remains_intact()
    print("Running test_pre_deployment_check_secrets_fails_on_error...")
    test_pre_deployment_check_secrets_fails_on_error()
    print("Running test_pre_deployment_check_secrets_succeeds_when_available...")
    test_pre_deployment_check_secrets_succeeds_when_available()
    print("\n[ALL 13 SECRETS MANAGER TESTS PASSED SUCCESSFULLY!]")
