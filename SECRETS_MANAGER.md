# Film Review Platform — AWS Secrets Manager Integration Guide

## 1. Overview
This project integrates **AWS Secrets Manager** (via **Floci** for local development) to eliminate plaintext credentials from `.env` and environment variables.

All sensitive application secrets are stored as a JSON payload in Secrets Manager:
- `DATABASE_PASSWORD`: Database user password
- `JWT_SECRET_KEY`: Symmetric key for signing and verifying JSON Web Tokens
- `THIRD_PARTY_API_KEY`: Optional third-party API key

Non-sensitive configurations (database host, database name, Redis URL, Floci endpoint) remain in `.env`.

---

## 2. Secrets Manager Structure
The application looks for a secret with SecretId `film-review/platform` (configurable via `AWS_SECRET_ID`).

### Secret JSON Schema:
```json
{
  "DATABASE_PASSWORD": "password",
  "JWT_SECRET_KEY": "development-secret-key-12345",
  "THIRD_PARTY_API_KEY": "optional-api-key"
}
```

---

## 3. Local Setup with Floci in PowerShell

Ensure Floci is running (e.g. via Docker Compose `docker compose up -d floci` or standalone on port 4566).

### Create the Secret in Floci:
```powershell
$ENDPOINT = "http://localhost:4566"
$SECRET_ID = "film-review/platform"
$SECRET_DATA = '{"DATABASE_PASSWORD":"password","JWT_SECRET_KEY":"development-secret-key-12345","THIRD_PARTY_API_KEY":"optional-api-key"}'

aws secretsmanager create-secret `
  --name $SECRET_ID `
  --secret-string $SECRET_DATA `
  --endpoint-url $ENDPOINT `
  --profile floci
```

### Retrieve and Verify the Secret in CLI:
```powershell
aws secretsmanager get-secret-value `
  --secret-id $SECRET_ID `
  --endpoint-url $ENDPOINT `
  --profile floci `
  --query "SecretString" `
  --output text
```

### Visual Verification in Floci Web Console:
Open your browser and navigate to:
```text
http://localhost:4566/_floci/ui
```
(or `http://localhost:4500`). Go to the **Secrets Manager** section and confirm `film-review/platform` appears with the stored keys.

---

## 4. Module Architecture & In-Memory Caching

- **`core/secrets.py`**:
  The **single module** that imports `boto3`. It connects to Secrets Manager, parses the JSON payload, validates non-empty fields, and stores the values in `_CACHED_SECRETS`. Subsequent calls return the cached values in memory without querying the network.
- **`core/config.py`**:
  Exposes `settings.DATABASE_URL` (assembled dynamically using `DATABASE_PASSWORD`) and `settings.TOKEN_SECRET_KEY`. No routes, DAOs, or handlers need modification.
- **`main.py`**:
  Calls `get_secrets()` in its `lifespan` hook. If Secrets Manager is unreachable or access is denied, application startup halts immediately.
- **`pre_deployment.sh`**:
  Runs `python pre_deployment/check_secrets.py` as Gate 2 before database and Redis checks.

---

## 5. Running Tests

Run the test suite:
```powershell
cd Day4
uv run python tests/test_secrets_manager.py
```
Or with pytest:
```powershell
uv run pytest tests/test_secrets_manager.py
```
All unit tests mock `boto3` calls with `unittest.mock.patch`, requiring zero connection to real AWS or Floci.

