"""
Integration tests for User Authentication flow using async test database and AsyncClient.
Tests cover:
1. Registration with valid payload
2. Login to retrieve access & refresh tokens in expected shape
3. Authenticated request using Bearer access token (/users/me)
"""

import pytest
from httpx import AsyncClient


@pytest.mark.integration
async def test_user_registration_login_and_auth_request_flow(async_client: AsyncClient):
    """
    Exercise complete user lifecycle:
    1. Register new user
    2. Login with credentials to receive tokens
    3. Make authenticated request to /users/me using Bearer token
    """
    # 1. Register a new user
    register_payload = {
        "username": "integ_tester",
        "email": "tester@example.com",
        "password": "SecurePassword123!",
        "role": "viewer",
    }
    reg_response = await async_client.post("/api/v1/register", json=register_payload)
    assert reg_response.status_code == 201
    user_data = reg_response.json()
    assert user_data["username"] == "integ_tester"
    assert user_data["email"] == "tester@example.com"
    assert user_data["role"] == "viewer"
    assert "password" not in user_data
    assert "password_hash" not in user_data

    # 2. Login to retrieve access & refresh tokens
    login_payload = {
        "username": "integ_tester",
        "password": "SecurePassword123!",
    }
    login_response = await async_client.post("/api/v1/login", json=login_payload)
    assert login_response.status_code == 200
    token_data = login_response.json()
    assert "access_token" in token_data
    assert "refresh_token" in token_data
    assert token_data.get("token_type") == "bearer"

    access_token = token_data["access_token"]
    assert len(access_token) > 20

    # 3. Make authenticated request with Bearer token to /api/v1/users/me
    auth_headers = {"Authorization": f"Bearer {access_token}"}
    me_response = await async_client.get("/api/v1/users/me", headers=auth_headers)
    assert me_response.status_code == 200

    me_data = me_response.json()
    assert me_data["username"] == "integ_tester"
    assert me_data["email"] == "tester@example.com"
    assert me_data["role"] == "viewer"


@pytest.mark.integration
async def test_token_refresh_and_logout_revocation_lifecycle(async_client: AsyncClient):
    """
    Test 1: Token Refresh & Redis Session Invalidation Flow
    1. Register & login to obtain access and refresh tokens.
    2. Call /refresh with the refresh token -> 200 OK and receives new access token.
    3. Use the new access token to access a protected endpoint -> 200 OK.
    4. Call /logout with access token -> 200 OK (revokes refresh token in Redis).
    5. Attempt /refresh again with the revoked refresh token -> 401 Unauthorized.
    """
    # Step 1: Register and login
    register_payload = {
        "username": "token_lifecycle_user",
        "email": "token_lifecycle@example.com",
        "password": "SecurePassword123!",
        "role": "viewer",
    }
    reg_res = await async_client.post("/api/v1/register", json=register_payload)
    assert reg_res.status_code == 201

    login_res = await async_client.post(
        "/api/v1/login",
        json={"username": "token_lifecycle_user", "password": "SecurePassword123!"},
    )
    assert login_res.status_code == 200
    token_data = login_res.json()
    old_access_token = token_data["access_token"]
    refresh_token = token_data["refresh_token"]

    # Step 2: Call /refresh with valid refresh token -> 200 OK
    refresh_headers = {"Authorization": f"Bearer {refresh_token}"}
    refresh_res = await async_client.post("/api/v1/refresh", headers=refresh_headers)
    assert refresh_res.status_code == 200
    new_token_data = refresh_res.json()
    assert "access_token" in new_token_data
    new_access_token = new_token_data["access_token"]
    assert len(new_access_token) > 20

    # Step 3: Confirm new access token works on protected route
    new_auth_headers = {"Authorization": f"Bearer {new_access_token}"}
    me_res = await async_client.get("/api/v1/users/me", headers=new_auth_headers)
    assert me_res.status_code == 200
    assert me_res.json()["username"] == "token_lifecycle_user"

    # Step 4: Logout using access token -> 200 OK
    logout_res = await async_client.post("/api/v1/logout", headers=new_auth_headers)
    assert logout_res.status_code == 200

    # Step 5: Subsequent call to /refresh with revoked refresh token must be rejected -> 401
    revoked_refresh_res = await async_client.post("/api/v1/refresh", headers=refresh_headers)
    assert revoked_refresh_res.status_code == 401


@pytest.mark.integration
async def test_jwt_verification_expired_and_tampered_rejection(async_client: AsyncClient):
    """
    Test 2: Expired and Tampered JWT Rejection
    Verifies that the API rigorously validates token cryptography, expiration, and format:
    1. Expired token -> 401 Unauthorized
    2. Tampered signature (wrong secret key) -> 401 Unauthorized
    3. Missing / Malformed Authorization header -> 401 Unauthorized
    4. Type mismatch: Passing refresh token to an access-token protected route -> 401 Unauthorized
    """
    from datetime import timedelta
    from jose import jwt
    from core.security import create_access_token, create_refresh_token, ALGORITHM

    # 1. Expired token rejection
    expired_token = create_access_token(
        data={"sub": "11111111-1111-1111-1111-111111111111", "username": "expired_user", "role": "viewer"},
        expires_delta=timedelta(seconds=-10),  # expired 10 seconds ago
    )
    res_expired = await async_client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert res_expired.status_code == 401

    # 2. Tampered token rejection (forged signature / wrong secret)
    tampered_token = jwt.encode(
        {"sub": "11111111-1111-1111-1111-111111111111", "username": "hacker", "role": "admin", "type": "access"},
        "wrong-secret-key-that-does-not-match",
        algorithm=ALGORITHM,
    )
    res_tampered = await async_client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {tampered_token}"})
    assert res_tampered.status_code == 401

    # 3. Missing and malformed Authorization header
    res_no_auth = await async_client.get("/api/v1/users/me")
    assert res_no_auth.status_code == 401

    res_garbage = await async_client.get("/api/v1/users/me", headers={"Authorization": "Bearer not-a-valid-token"})
    assert res_garbage.status_code == 401

    # 4. Refresh token passed to access-only protected route
    refresh_token = create_refresh_token(
        data={"sub": "11111111-1111-1111-1111-111111111111", "username": "test_user", "role": "viewer"}
    )
    res_wrong_type = await async_client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {refresh_token}"})
    assert res_wrong_type.status_code == 401

