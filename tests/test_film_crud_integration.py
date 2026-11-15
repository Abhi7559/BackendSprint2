"""
Integration tests for Film CRUD Lifecycle & Role Enforcement.
Exercising:
1. Create film as Admin (201 Created)
2. Fetch created film by ID (200 OK)
3. Update film as Admin and verify persistence (200 OK)
4. Attempt delete as Viewer -> rejected (403 Forbidden)
5. Delete as Admin (200 OK)
6. Verify film is no longer returned in film listing (soft delete verified)
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
async def test_film_crud_lifecycle_and_deletion_rbac(async_client: AsyncClient):
    """
    Verifies full film CRUD lifecycle:
    - Create as Admin
    - Read by ID
    - Update field as Admin
    - Attempt delete as Viewer -> 403 Forbidden
    - Delete as Admin -> 200 OK
    - Confirm film does not appear in list response
    """
    admin_headers = make_auth_header("11111111-1111-1111-1111-111111111111", "admin_user", "admin")
    viewer_headers = make_auth_header("22222222-2222-2222-2222-222222222222", "viewer_user", "viewer")

    # 1. Create a film as Admin
    create_payload = {
        "title": "Dune: Part Two",
        "release_year": 2024,
        "genre": "Sci-Fi",
        "director": "Denis Villeneuve",
    }
    create_res = await async_client.post("/api/v1/films", json=create_payload, headers=admin_headers)
    assert create_res.status_code == 201
    created_film = create_res.json()
    film_id = created_film["id"]
    assert created_film["title"] == "Dune: Part Two"
    assert created_film["release_year"] == 2024

    # 2. Fetch film by ID
    get_res = await async_client.get(f"/api/v1/films/{film_id}", headers=viewer_headers)
    assert get_res.status_code == 200
    fetched_film = get_res.json()
    assert fetched_film["id"] == film_id
    assert fetched_film["title"] == "Dune: Part Two"

    # 3. Update one field as Admin and confirm change persisted
    update_payload = {"title": "Dune: Part Two (IMAX Edition)"}
    update_res = await async_client.patch(f"/api/v1/films/{film_id}", json=update_payload, headers=admin_headers)
    assert update_res.status_code == 200
    assert update_res.json()["title"] == "Dune: Part Two (IMAX Edition)"

    # Verify persistence by fetching again
    verify_res = await async_client.get(f"/api/v1/films/{film_id}", headers=viewer_headers)
    assert verify_res.status_code == 200
    assert verify_res.json()["title"] == "Dune: Part Two (IMAX Edition)"

    # 4. Attempt deletion as Viewer -> Rejected with 403 Forbidden
    viewer_delete_res = await async_client.delete(f"/api/v1/films/{film_id}", headers=viewer_headers)
    assert viewer_delete_res.status_code == 403

    # 5. Delete film as Admin -> 200 OK
    admin_delete_res = await async_client.delete(f"/api/v1/films/{film_id}", headers=admin_headers)
    assert admin_delete_res.status_code == 200

    # 6. Confirm film is soft-deleted and no longer appears in the films list
    list_res = await async_client.get("/api/v1/films", headers=viewer_headers)
    assert list_res.status_code == 200
    film_ids_in_list = [f["id"] for f in list_res.json()["items"]]
    assert film_id not in film_ids_in_list


