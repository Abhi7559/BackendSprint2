"""
Unit tests for ReviewService business rules.
All external dependencies (FilmDAO, ReviewDAO, UserDAO) are mocked with AsyncMock.
Zero external infrastructure required (no live DB, no Redis, no network).
"""

import uuid
from unittest.mock import AsyncMock, patch
import pytest

from exceptions.domain import (
    DuplicateReviewError,
    FilmNotFoundError,
    ReviewNotFoundError,
    UnauthorisedReviewAccessError,
)
from models.film import Film
from models.review import Review
from models.user import User
from schemas.review import ReviewCreate, ReviewUpdate
from services.review_service import ReviewService

# Standard valid review text satisfying min_length=50
VALID_REVIEW_TEXT_1 = (
    "A breathtaking cinematic visual and emotional odyssey through space and time with unmatched depth."
)
VALID_REVIEW_TEXT_2 = (
    "A thrilling masterpiece of storytelling with unforgettable performances and impeccable direction."
)
VALID_REVIEW_UPDATE_TEXT = (
    "This is an updated review text that exceeds the required fifty character length validation threshold."
)


@pytest.mark.unit
def test_create_review_raises_film_not_found(critic_user: User):
    """
    Business Rule 1: A review cannot be created for a film that does not exist.
    Asserts FilmNotFoundError is raised carrying the exact missing film_id.
    """
    service = ReviewService()
    fake_session = AsyncMock()
    missing_film_id = uuid.uuid4()
    review_in = ReviewCreate(rating=9, body=VALID_REVIEW_TEXT_1)
    user_dict = {"username": critic_user.username, "role": critic_user.role}

    with patch("services.review_service.film_dao.get_by_id", new_callable=AsyncMock) as mock_get_film:
        mock_get_film.return_value = None

        with pytest.raises(FilmNotFoundError) as exc_info:
            import asyncio
            asyncio.run(service.create_review(fake_session, missing_film_id, review_in, user_dict))

        # Assert exact exception type and resource identifier carried by it
        assert exc_info.value.film_id == missing_film_id
        assert f"Film {missing_film_id} was not found." in str(exc_info.value)


@pytest.mark.unit
def test_create_review_rejects_duplicate_review_by_same_user(sample_film: Film, critic_user: User):
    """
    Business Rule 2: A user cannot review the same film twice.
    Asserts DuplicateReviewError is raised carrying user_id and film_id.
    """
    service = ReviewService()
    fake_session = AsyncMock()
    review_in = ReviewCreate(rating=8, body=VALID_REVIEW_TEXT_2)
    user_dict = {"username": critic_user.username, "role": critic_user.role}

    existing_review = Review(
        id=uuid.uuid4(),
        film_id=sample_film.id,
        user_id=critic_user.id,
        rating=9,
        review_body=VALID_REVIEW_TEXT_1,
    )

    with patch("services.review_service.film_dao.get_by_id", new_callable=AsyncMock) as mock_get_film, \
         patch("services.review_service.user_dao.get_by_username", new_callable=AsyncMock) as mock_get_user, \
         patch("services.review_service.review_dao.get_by_user_and_film", new_callable=AsyncMock) as mock_get_rev:

        mock_get_film.return_value = sample_film
        mock_get_user.return_value = critic_user
        mock_get_rev.return_value = existing_review

        with pytest.raises(DuplicateReviewError) as exc_info:
            import asyncio
            asyncio.run(service.create_review(fake_session, sample_film.id, review_in, user_dict))

        # Assert both resource identifiers on the exception
        assert exc_info.value.user_id == critic_user.id
        assert exc_info.value.film_id == sample_film.id
        assert "You have already reviewed this film." in str(exc_info.value)


@pytest.mark.unit
def test_update_review_rejected_for_non_owner(sample_review: Review, viewer_user: User):
    """
    Business Rule 3: A review update is rejected when attempted by a user other than the author.
    Asserts UnauthorisedReviewAccessError carrying review_id and current_user_id.
    """
    service = ReviewService()
    fake_session = AsyncMock()
    update_in = ReviewUpdate(rating=7, body=VALID_REVIEW_UPDATE_TEXT)

    # Current user is viewer_user, but review was authored by critic_user
    current_user_dict = {"username": viewer_user.username, "role": viewer_user.role, "user_id": viewer_user.id}

    with patch("services.review_service.review_dao.get_by_id", new_callable=AsyncMock) as mock_get_rev, \
         patch("services.review_service.user_dao.get_by_username", new_callable=AsyncMock) as mock_get_user:

        mock_get_rev.return_value = sample_review
        mock_get_user.return_value = viewer_user

        with pytest.raises(UnauthorisedReviewAccessError) as exc_info:
            import asyncio
            asyncio.run(service.update_review(fake_session, sample_review.id, update_in, current_user_dict))

        assert exc_info.value.review_id == sample_review.id
        assert exc_info.value.user_id == viewer_user.id
        assert f"User {viewer_user.id} is not allowed to modify review {sample_review.id}." in str(exc_info.value)


@pytest.mark.unit
def test_update_review_raises_not_found_when_missing():
    """
    Business Rule 4: Updating a non-existent review raises ReviewNotFoundError with the review_id.
    """
    service = ReviewService()
    fake_session = AsyncMock()
    missing_id = uuid.uuid4()
    update_in = ReviewUpdate(rating=8, body=VALID_REVIEW_UPDATE_TEXT)

    with patch("services.review_service.review_dao.get_by_id", new_callable=AsyncMock) as mock_get_rev:
        mock_get_rev.return_value = None

        with pytest.raises(ReviewNotFoundError) as exc_info:
            import asyncio
            asyncio.run(service.update_review(fake_session, missing_id, update_in, {"username": "admin", "role": "admin"}))

        assert exc_info.value.review_id == missing_id
        assert f"Review {missing_id} was not found." in str(exc_info.value)
