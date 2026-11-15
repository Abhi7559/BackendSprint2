"""
Comprehensive Mocking, Patching, and Unit/Integration Tests for:
1. Redis caching layer (cache hit vs miss, DB queried or skipped, data stored with TTL)
2. Logout endpoint key deletion (verifying exact Redis key deleted and called count)
3. Centralized domain exception handlers (HTTP status, type field, non-empty message)
4. Background aggregation task (_recalculate_film_stats_bg) direct invocation verifying film stats update
"""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from core.security import create_access_token
from dao.film_dao import film_dao
from exceptions.domain import (
    DuplicateReviewError,
    EmailAlreadyExistsError,
    FilmHasActiveReviewsError,
    FilmNotFoundError,
    ForbiddenError,
    InvalidCredentialsError,
    InvalidTokenError,
    ReviewNotFoundError,
    UnauthorisedReviewAccessError,
    UsernameAlreadyExistsError,
)
from models.film import Film
from models.review import Review
from models.user import User
from routes.reviews import _recalculate_film_stats_bg
from schemas.film import FilmResponse
from services.film_service import FilmService
from services.user_service import UserService


# ===========================================================================
# 1. Tests for the Redis Caching Layer
# ===========================================================================

@pytest.mark.unit
async def test_redis_cache_miss_queries_db_and_populates_cache(mocker):
    """
    On simulated cache miss (redis.get returns None):
    1. Database DAO (film_dao.list) is queried.
    2. Serialized result is written to Redis via redis.set with TTL.
    3. Returns fetched serialized films.
    """
    service = FilmService()
    fake_session = AsyncMock()

    # Create mock Redis client using pytest-mock's mocker fixture
    mock_redis = mocker.AsyncMock()
    mock_redis.get.return_value = None  # Cache MISS

    sample_film_obj = Film(
        id=uuid.uuid4(),
        title="Oppenheimer",
        release_year=2023,
        genre="Drama",
        director="Christopher Nolan",
        is_deleted=False,
        review_count=5,
        average_rating=4.8,
    )

    # Mock film_dao.list
    mock_dao_list = mocker.patch(
        "services.film_service.film_dao.list",
        new_callable=mocker.AsyncMock,
        return_value=[sample_film_obj],
    )

    # Execute service method
    result = await service.get_all_films(
        session=fake_session,
        redis=mock_redis,
        genre="Drama",
    )

    # Assertions
    expected_cache_key = "films:list:genre=Drama:start=None:end=None"
    mock_redis.get.assert_awaited_once_with(expected_cache_key)
    mock_dao_list.assert_awaited_once_with(
        fake_session,
        genre="Drama",
        start_year=None,
        end_year=None,
    )
    mock_redis.set.assert_awaited_once()
    set_args, set_kwargs = mock_redis.set.call_args
    assert set_args[0] == expected_cache_key
    assert "Oppenheimer" in set_args[1]
    assert set_kwargs.get("ex") == 300  # Default TTL (FILM_LIST_CACHE_TTL_SECONDS)

    assert len(result) == 1
    assert result[0]["title"] == "Oppenheimer"


@pytest.mark.unit
async def test_redis_cache_hit_returns_cached_data_without_querying_db(mocker):
    """
    On simulated cache hit (redis.get returns serialized JSON):
    1. Result is deserialized and returned directly.
    2. Database DAO (film_dao.list) is NEVER queried.
    3. redis.set is NEVER called.
    """
    service = FilmService()
    fake_session = AsyncMock()

    cached_payload = [
        {
            "id": str(uuid.uuid4()),
            "title": "Interstellar",
            "release_year": 2014,
            "genre": "Sci-Fi",
            "director": "Christopher Nolan",
            "review_count": 10,
            "average_rating": 4.9,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }
    ]

    mock_redis = mocker.AsyncMock()
    mock_redis.get.return_value = json.dumps(cached_payload)  # Cache HIT

    mock_dao_list = mocker.patch(
        "services.film_service.film_dao.list",
        new_callable=mocker.AsyncMock,
    )

    result = await service.get_all_films(
        session=fake_session,
        redis=mock_redis,
        genre="Sci-Fi",
    )

    expected_cache_key = "films:list:genre=Sci-Fi:start=None:end=None"
    mock_redis.get.assert_awaited_once_with(expected_cache_key)
    # Critical verification: Database was never touched
    mock_dao_list.assert_not_called()
    mock_redis.set.assert_not_called()

    assert result == cached_payload


# ===========================================================================
# 2. Test for the Logout Endpoint (Redis key deletion assertion)
# ===========================================================================

@pytest.mark.unit
async def test_logout_service_deletes_exact_redis_key():
    """
    Unit test on UserService:
    Asserts that redis.delete is awaited with the exact target refresh_token key
    and called exactly once.
    """
    service = UserService()
    mock_redis = AsyncMock()
    user_id = str(uuid.uuid4())
    expected_redis_key = f"refresh_token:{user_id}"

    response = await service.logout_user(user_id=user_id, redis=mock_redis)

    assert response == {"message": "Successfully logged out."}
    mock_redis.delete.assert_awaited_once_with(expected_redis_key)
    assert mock_redis.delete.await_count == 1


@pytest.mark.integration
async def test_logout_endpoint_verifies_redis_key_deletion_and_call_count(mocker):
    """
    Integration-level test for POST /api/v1/logout:
    Uses a mock Redis client injected into the endpoint to verify:
    1. Exact Redis key targeted: 'refresh_token:<user_id>'
    2. Number of times deletion was called: exactly 1 time
    3. Status code 200 OK and expected message
    """
    from main import app
    from dependencies.redis import get_redis

    test_user_id = str(uuid.uuid4())
    token = create_access_token({
        "sub": test_user_id,
        "username": "logout_test_user",
        "email": "logout@example.com",
        "role": "viewer",
    })

    mock_redis = mocker.AsyncMock()

    # Override get_redis with our mock
    async def override_get_redis():
        yield mock_redis

    app.dependency_overrides[get_redis] = override_get_redis

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/logout",
            headers={"Authorization": f"Bearer {token}"},
        )

    app.dependency_overrides.clear()

    # Verify HTTP response
    assert response.status_code == 200
    assert response.json() == {"message": "Successfully logged out."}

    # Verify exact key and call count on mock
    expected_key = f"refresh_token:{test_user_id}"
    mock_redis.delete.assert_awaited_once_with(expected_key)
    assert mock_redis.delete.await_count == 1


# ===========================================================================
# 3. Tests for Centralized Exception Handlers
# ===========================================================================

@pytest.mark.parametrize(
    "exception_instance,expected_status,expected_type",
    [
        (FilmNotFoundError(film_id=uuid.UUID("11111111-1111-1111-1111-111111111111")), 404, "FilmNotFoundError"),
        (ReviewNotFoundError(review_id=uuid.UUID("22222222-2222-2222-2222-222222222222")), 404, "ReviewNotFoundError"),
        (
            DuplicateReviewError(
                user_id=uuid.UUID("33333333-3333-3333-3333-333333333333"),
                film_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
            ),
            409,
            "DuplicateReviewError",
        ),
        (
            UnauthorisedReviewAccessError(
                review_id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
                user_id=uuid.UUID("33333333-3333-3333-3333-333333333333"),
            ),
            403,
            "UnauthorisedReviewAccessError",
        ),
        (FilmHasActiveReviewsError(film_id=uuid.UUID("11111111-1111-1111-1111-111111111111")), 409, "FilmHasActiveReviewsError"),
        (ForbiddenError(detail="Custom forbidden error"), 403, "ForbiddenError"),
        (UsernameAlreadyExistsError(username="existing_user"), 400, "UsernameAlreadyExistsError"),
        (EmailAlreadyExistsError(email="existing@example.com"), 400, "EmailAlreadyExistsError"),
        (InvalidCredentialsError(), 401, "InvalidCredentialsError"),
        (InvalidTokenError(detail="Token has expired"), 401, "InvalidTokenError"),
    ],
)
async def test_centralized_exception_handler_status_type_and_message(
    exception_instance,
    expected_status: int,
    expected_type: str,
):
    """
    Trigger domain exceptions from within an application route and assert that the response:
    1. Carries the correct HTTP status code
    2. Contains the expected 'type' field value
    3. Contains a non-empty 'message' string
    """
    from fastapi import FastAPI
    from exceptions.handlers import register_exception_handlers

    test_app = FastAPI()
    register_exception_handlers(test_app)

    @test_app.get("/trigger-error")
    async def trigger_error():
        raise exception_instance

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/trigger-error")

    assert response.status_code == expected_status
    body = response.json()
    assert body.get("type") == expected_type
    assert isinstance(body.get("message"), str)
    assert len(body["message"].strip()) > 0


# ===========================================================================
# 4. Direct Invocation Test for the Background Aggregation Task
# ===========================================================================

@pytest.mark.integration
async def test_background_aggregation_task_direct_invocation(db_session):
    """
    Direct invocation test for the background aggregation task:
    1. Set up a film and multiple reviews with known ratings in the test database.
    2. Directly call `_recalculate_film_stats_bg(film_id)` (or film_dao.recalculate_review_stats).
    3. Query the test database to confirm review_count and average_rating
       match the exact calculated values from the reviews.
    """
    # 1. Create a test user for authoring reviews
    user_id = uuid.uuid4()
    test_user = User(
        id=user_id,
        username="stats_reviewer",
        email="stats_reviewer@example.com",
        password_hash="fakehash",
        role="critic",
    )
    db_session.add(test_user)

    # 2. Create a test film with initial 0 reviews and None rating
    film_id = uuid.uuid4()
    test_film = Film(
        id=film_id,
        title="Aggregation Inception",
        release_year=2010,
        genre="Sci-Fi",
        director="Christopher Nolan",
        review_count=0,
        average_rating=None,
    )
    db_session.add(test_film)
    await db_session.flush()

    # 3. Add reviews for this film: ratings 4 and 5 -> count=2, average=(4+5)/2 = 4.5
    review1 = Review(
        id=uuid.uuid4(),
        film_id=film_id,
        user_id=user_id,
        rating=4,
        review_body="A mind-bending cinematic spectacle that keeps you guessing until the end.",
    )
    # Add a second reviewer
    user_id_2 = uuid.uuid4()
    test_user_2 = User(
        id=user_id_2,
        username="stats_reviewer_2",
        email="stats_reviewer_2@example.com",
        password_hash="fakehash",
        role="critic",
    )
    db_session.add(test_user_2)
    review2 = Review(
        id=uuid.uuid4(),
        film_id=film_id,
        user_id=user_id_2,
        rating=5,
        review_body="An absolute masterpiece of modern cinema with breathtaking practical effects.",
    )
    db_session.add_all([review1, review2])
    await db_session.commit()

    # 4. Directly invoke the background task helper function
    # Provide a session factory that uses the test transaction session
    from database.engine import set_session_factory, SessionLocal
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def session_override():
        yield db_session

    set_session_factory(lambda: session_override())
    try:
        await _recalculate_film_stats_bg(film_id)
    finally:
        set_session_factory(SessionLocal)

    # 5. Query the database afresh to confirm film's review_count and average_rating
    query = select(Film).where(Film.id == film_id)
    result = await db_session.execute(query)
    updated_film = result.scalar_one()

    assert updated_film.review_count == 2
    assert updated_film.average_rating == 4.5


# ===========================================================================
# 5. Targeted Tests for Identified Code Coverage Gaps
# ===========================================================================

@pytest.mark.unit
def test_coverage_gap_1_release_window_validator():
    """
    Gap 1: schemas/film.py: ReleaseWindow model_validator branch where
    start_year > end_year raises ValueError.
    """
    from pydantic import ValidationError
    from schemas.film import ReleaseWindow

    # Valid window
    valid_window = ReleaseWindow(start_year=2000, end_year=2010)
    assert valid_window.start_year == 2000
    assert valid_window.end_year == 2010

    # Invalid window: start_year > end_year triggers validation branch
    with pytest.raises(ValidationError) as exc_info:
        ReleaseWindow(start_year=2024, end_year=2020)

    assert "start_year must be less than or equal to end_year" in str(exc_info.value)


@pytest.mark.integration
async def test_coverage_gap_2_refresh_without_token_raises_invalid_token(async_client: AsyncClient):
    """
    Gap 2: routes/users.py: POST /api/v1/refresh missing Authorization header
    triggers the branch raising InvalidTokenError and returns 401.
    """
    response = await async_client.post("/api/v1/refresh")
    assert response.status_code == 401
    body = response.json()
    assert body.get("type") == "InvalidTokenError"
    assert "Authorization Bearer refresh token is missing" in body.get("message", "")


@pytest.mark.integration
async def test_coverage_gap_3_get_review_by_id_route(async_client: AsyncClient, db_session):
    """
    Gap 3: routes/reviews.py: GET /api/v1/reviews/{review_id}
    Retrieves a review and serializes via _to_review_response.
    """
    # Create user, film, and review
    critic_id = uuid.uuid4()
    critic = User(
        id=critic_id,
        username="gap_critic",
        email="gap_critic@example.com",
        password_hash="fakehash",
        role="critic",
    )
    film_id = uuid.uuid4()
    film = Film(
        id=film_id,
        title="Coverage Film",
        release_year=2022,
        genre="Action",
        director="Test Director",
    )
    db_session.add_all([critic, film])
    await db_session.flush()

    review_id = uuid.uuid4()
    review = Review(
        id=review_id,
        film_id=film_id,
        user_id=critic_id,
        rating=5,
        review_body="An unforgettable cinematic experience with phenomenal storytelling and acting.",
    )
    db_session.add(review)
    await db_session.commit()

    token = create_access_token({
        "sub": str(critic_id),
        "username": "gap_critic",
        "email": "gap_critic@example.com",
        "role": "critic",
    })

    response = await async_client.get(
        f"/api/v1/reviews/{review_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(review_id)
    assert data["film_id"] == str(film_id)
    assert data["rating"] == 5
    assert data["reviewer_name"] == "gap_critic"

