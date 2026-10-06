import uuid
from collections.abc import Sequence
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from models.review import Review


class ReviewDAO:
    """
    Data Access Object for Review entity.
    Encapsulates all direct database queries for Review using SQLAlchemy 2.0 async syntax.
    """

    async def list_by_film(self, session: AsyncSession, film_id: uuid.UUID) -> Sequence[Review]:
        """
        List all reviews for a given film ordered by most recent first (created_at desc).
        Eagerly loads user details to prevent N+1 queries.
        Returns an empty list if there are no reviews.
        """
        stmt = (
            select(Review)
            .options(
                joinedload(Review.user),
                joinedload(Review.film),
            )
            .where(Review.film_id == film_id)
            .order_by(Review.created_at.desc())
        )
        result = await session.execute(stmt)
        return result.scalars().all()

    # Alias for backward-compatibility
    async def get_by_film_id(self, session: AsyncSession, film_id: uuid.UUID) -> Sequence[Review]:
        return await self.list_by_film(session, film_id)

    async def average_rating(self, session: AsyncSession, film_id: uuid.UUID) -> float | None:
        """
        Compute the average rating across all reviews for a given film using SQL AVG.
        Returns None when there are no reviews (does not return 0).
        """
        stmt = select(func.avg(Review.rating)).where(Review.film_id == film_id)
        result = await session.execute(stmt)
        avg = result.scalar()
        return float(avg) if avg is not None else None

    async def get_all_with_film_and_user(self, session: AsyncSession) -> Sequence[Review]:
        """
        Fetch all reviews across films with user and film relationships eagerly loaded.
        """
        stmt = (
            select(Review)
            .options(
                joinedload(Review.film),
                joinedload(Review.user),
            )
            .order_by(Review.created_at.desc())
        )
        result = await session.execute(stmt)
        return result.scalars().all()

    async def get_by_id(self, session: AsyncSession, review_id: uuid.UUID) -> Review | None:
        """Fetch a single review by ID with film and user relationships loaded."""
        stmt = (
            select(Review)
            .options(
                joinedload(Review.user),
                joinedload(Review.film),
            )
            .where(Review.id == review_id)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self,
        session: AsyncSession,
        review: Review | None = None,
        film_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
        rating: int | None = None,
        review_body: str | None = None,
    ) -> Review:
        """
        Create a new review.
        Supports passing either a Review model instance or individual fields.
        """
        if isinstance(review, Review):
            review_record = review
        else:
            if film_id is None or user_id is None or rating is None or review_body is None:
                raise ValueError("film_id, user_id, rating, and review_body are required when review instance is not provided")
            review_record = Review(
                film_id=film_id,
                user_id=user_id,
                rating=rating,
                review_body=review_body,
            )

        session.add(review_record)
        await session.commit()
        await session.refresh(review_record)
        reloaded = await self.get_by_id(session, review_record.id)
        return reloaded if reloaded is not None else review_record

    async def update(
        self,
        session: AsyncSession,
        review_id: uuid.UUID,
        rating: int | None = None,
        review_body: str | None = None,
    ) -> Review | None:
        """Update an existing review."""
        review = await self.get_by_id(session, review_id)
        if not review:
            return None
        if rating is not None:
            review.rating = rating
        if review_body is not None:
            review.review_body = review_body
        await session.commit()
        await session.refresh(review)
        return review

    async def delete(self, session: AsyncSession, review_id: uuid.UUID) -> bool:
        """
        Physically delete a review by ID.
        Returns True when deleted, False when not found.
        """
        review = await self.get_by_id(session, review_id)
        if not review:
            return False
        await session.delete(review)
        await session.commit()
        return True

    async def count_reviews(self, session: AsyncSession) -> int:
        """Count total reviews in the system."""
        stmt = select(func.count(Review.id))
        result = await session.execute(stmt)
        return result.scalar() or 0

    async def get_by_user_and_film(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        film_id: uuid.UUID,
    ) -> Review | None:
        """Fetch review for a specific user and film."""
        stmt = select(Review).where(
            Review.user_id == user_id,
            Review.film_id == film_id,
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def has_active_reviews(
        self,
        session: AsyncSession,
        film_id: uuid.UUID,
    ) -> bool:
        """Check if a film has any active reviews."""
        # Note: Review model does not have is_active or is_deleted column, so all existing reviews are active
        stmt = select(Review.id).where(Review.film_id == film_id).limit(1)
        result = await session.execute(stmt)
        return result.first() is not None


# Global DAO instance
review_dao = ReviewDAO()
