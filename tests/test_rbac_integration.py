"""
Integration tests for Role-Based Access Control (RBAC) enforcement across endpoints.
Tests verify both:
- Permitted Case (Authorized role gets expected success status & body)
- Forbidden Case (Unauthorized role gets 403 Forbidden rejection status)

Endpoints tested:
1. POST /api/v1/films/{film_id}/reviews (Only Admin and Critic permitted; Viewer rejected with 403)
2. GET /api/v1/admin/stats (Only Admin permitted; Viewer and Critic rejected with 403)
"""

import pytest
from httpx import AsyncClient
from core.security import create_access_token


def make_auth_header(user_id: str, username: str, role: str) -> dict[str, str]:
    """Helper to generate JWT Authorization Bearer header for any test role."""
    token = create_access_token({
        "sub": user_id,
        "username": username,
        "email": f"{username}@example.com",
        "role": role,
    })
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.integration
async def test_review_creation_role_enforcement(async_client: AsyncClient):
    """
    Endpoint Pair 1: POST /api/v1/films/{film_id}/reviews
    - Permitted case: Critic submits review -> 201 Created with valid review data
    - Forbidden case: Viewer attempts to submit review -> 403 Forbidden
    """
    admin_headers = make_auth_header("11111111-1111-1111-1111-111111111111", "admin_user", "admin")
    critic_headers = make_auth_header("33333333-3333-3333-3333-333333333333", "critic_user", "critic")
    viewer_headers = make_auth_header("22222222-2222-2222-2222-222222222222", "viewer_user", "viewer")

    # Step 1: Create a film to review
    film_res = await async_client.post(
        "/api/v1/films",
        json={"title": "Oppenheimer", "release_year": 2023, "genre": "Drama", "director": "Christopher Nolan"},
        headers=admin_headers,
    )
    assert film_res.status_code == 201
    film_id = film_res.json()["id"]

    valid_review_body = "This is a detailed, compelling, and thought-provoking cinematic masterpiece that exceeds expectations."

    # Step 2: Forbidden case - Viewer attempts to create review -> 403
    forbidden_res = await async_client.post(
        f"/api/v1/films/{film_id}/reviews",
        json={"rating": 9, "body": valid_review_body},
        headers=viewer_headers,
    )
    assert forbidden_res.status_code == 403

    # Step 3: Permitted case - Critic creates review -> 201 Created
    permitted_res = await async_client.post(
        f"/api/v1/films/{film_id}/reviews",
        json={"rating": 9, "body": valid_review_body},
        headers=critic_headers,
    )
    assert permitted_res.status_code == 201
    review_data = permitted_res.json()
    assert review_data["rating"] == 9
    assert review_data["body"] == valid_review_body
    assert review_data["reviewer_name"] == "critic_user"


@pytest.mark.integration
async def test_admin_stats_role_enforcement(async_client: AsyncClient):
    """
    Endpoint Pair 2: GET /api/v1/admin/stats
    - Forbidden case: Critic / Viewer attempts to view admin stats -> 403 Forbidden
    - Permitted case: Admin accesses stats -> 200 OK with total_users & total_reviews counts
    """
    admin_headers = make_auth_header("11111111-1111-1111-1111-111111111111", "admin_user", "admin")
    critic_headers = make_auth_header("33333333-3333-3333-3333-333333333333", "critic_user", "critic")

    # Forbidden case: Critic tries to view admin stats -> 403
    forbidden_res = await async_client.get("/api/v1/admin/stats", headers=critic_headers)
    assert forbidden_res.status_code == 403

    # Permitted case: Admin views stats -> 200 OK
    permitted_res = await async_client.get("/api/v1/admin/stats", headers=admin_headers)
    assert permitted_res.status_code == 200
    stats_data = permitted_res.json()
    assert "total_users" in stats_data
    assert "total_reviews" in stats_data
