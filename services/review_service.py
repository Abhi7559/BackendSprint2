import logging
from collections.abc import Sequence
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from dao.film_dao import film_dao
from dao.review_dao import review_dao
from dao.user_dao import user_dao
from exceptions.domain import (
    DuplicateReviewError,
    FilmNotFoundError,
    ReviewNotFoundError,
    UnauthorisedReviewAccessError,
)
from models.review import Review
from schemas.review import ReviewCreate, ReviewUpdate

logger = logging.getLogger(__name__)


class ReviewService:
    """
    Service layer for reviews.
    Orchestrates business logic and calls ReviewDAO, FilmDAO, and UserDAO.
    Does not execute direct DB queries.
    """

    async def get_reviews_by_film_id(self, session: AsyncSession, film_id: UUID) -> Sequence[Review]:
        return await review_dao.list_by_film(session, film_id)

    async def get_review_by_id(self, session: AsyncSession, review_id: UUID) -> Review:
        review = await review_dao.get_by_id(session, review_id)
        if not review:
            raise ReviewNotFoundError(review_id=review_id)
        return review

    async def get_average_rating(self, session: AsyncSession, film_id: UUID) -> float | None:
        film = await film_dao.get_by_id(session, film_id)
        if not film:
            raise FilmNotFoundError(film_id=film_id)
        return await review_dao.average_rating(session, film_id)

    async def create_review(
        self,
        session: AsyncSession,
        film_id: UUID,
        review_data: ReviewCreate,
        current_user_dict: dict,
    ) -> Review:
        """
        Create a new review for a film.
        Business Rules:
        1. Check whether the film exists. If not -> FilmNotFoundError
        2. Check whether the user already reviewed the film. If yes -> DuplicateReviewError
        """
        film = await film_dao.get_by_id(session, film_id)
        if not film:
            raise FilmNotFoundError(film_id=film_id)

        user = await user_dao.get_by_username(session, current_user_dict["username"])
        if not user:
            user = await user_dao.create(
                session=session,
                username=current_user_dict["username"],
                email=f"{current_user_dict['username']}@example.com",
                role=current_user_dict.get("role", "user"),
            )

        logger.info(f"Creating review for film {film_id} by user {user.id}.")

        # Business rule: One review per user per film
        existing_review = await review_dao.get_by_user_and_film(session, user.id, film_id)
        if existing_review:
            logger.warning(f"User {user.id} already reviewed film {film_id}.")
            raise DuplicateReviewError(user_id=user.id, film_id=film_id)

        created = await review_dao.create(
            session=session,
            film_id=film_id,
            user_id=user.id,
            rating=review_data.rating,
            review_body=review_data.body,
        )
        logger.info(f"Review created successfully with id {created.id}.")
        return created

    async def update_review(
        self,
        session: AsyncSession,
        review_id: UUID,
        review_data: ReviewUpdate,
        current_user_dict: dict | None = None,
    ) -> Review:
        """
        Update an existing review.
        Business Rules:
        1. Find the review. If not found -> ReviewNotFoundError
        2. If current_user provided, verify review.user_id == current_user.id.
           If different -> UnauthorisedReviewAccessError
        3. Update rating / body.
        """
        review = await review_dao.get_by_id(session, review_id)
        if not review:
            raise ReviewNotFoundError(review_id=review_id)

        # Check ownership if current_user_dict is provided
        if current_user_dict:
            user = await user_dao.get_by_username(session, current_user_dict["username"])
            current_user_id = user.id if user else current_user_dict.get("user_id")
            if current_user_id and review.user_id != current_user_id:
                logger.warning(
                    f"User {current_user_id} attempted to modify review {review_id} owned by another user."
                )
                raise UnauthorisedReviewAccessError(review_id=review_id, user_id=current_user_id)

        logger.info(f"Updating review {review_id}.")
        updated = await review_dao.update(
            session=session,
            review_id=review_id,
            rating=review_data.rating,
            review_body=review_data.body,
        )
        if not updated:
            raise ReviewNotFoundError(review_id=review_id)

        logger.info(f"Review {review_id} updated successfully.")
        return updated

    async def delete_review(self, session: AsyncSession, review_id: UUID) -> bool:
        review = await review_dao.get_by_id(session, review_id)
        if not review:
            raise ReviewNotFoundError(review_id=review_id)

        await review_dao.delete(session, review_id)
        logger.info(f"Review {review_id} deleted successfully.")
        return True


review_service = ReviewService()
