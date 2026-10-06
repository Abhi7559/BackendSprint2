from collections.abc import Sequence
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from models.review import Review
from schemas.review import ReviewCreate, ReviewUpdate
from services.review_service import review_service


class ReviewHandler:
    """
    Handler layer for reviews.
    Delegates to ReviewService. Does not call DAOs directly and does not execute database queries.
    """

    async def get_reviews_by_film_id(self, session: AsyncSession, film_id: UUID) -> Sequence[Review]:
        return await review_service.get_reviews_by_film_id(session, film_id)

    async def get_average_rating(self, session: AsyncSession, film_id: UUID) -> float | None:
        return await review_service.get_average_rating(session, film_id)

    async def get_review_by_id(self, session: AsyncSession, review_id: UUID) -> Review:
        return await review_service.get_review_by_id(session, review_id)

    async def create_review(
        self,
        session: AsyncSession,
        film_id: UUID,
        review_data: ReviewCreate,
        current_user_dict: dict,
    ) -> Review:
        return await review_service.create_review(session, film_id, review_data, current_user_dict)

    async def update_review(
        self,
        session: AsyncSession,
        review_id: UUID,
        review_data: ReviewUpdate,
        current_user_dict: dict | None = None,
    ) -> Review:
        return await review_service.update_review(session, review_id, review_data, current_user_dict)

    async def delete_review(self, session: AsyncSession, review_id: UUID) -> bool:
        return await review_service.delete_review(session, review_id)


review_handler = ReviewHandler()

