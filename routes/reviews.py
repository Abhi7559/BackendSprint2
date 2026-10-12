from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies.auth import get_current_user, require_role
from dependencies.database import get_db
from dependencies.trace import get_trace_id
from exceptions.domain import UserRole
from handlers.review_handler import review_handler
from schemas.review import (
    ReviewCreate,
    ReviewDeleteResponse,
    ReviewResponse,
    ReviewUpdate,
)

router = APIRouter(
    tags=["Reviews"],
    dependencies=[Depends(get_current_user)],
)


def _to_review_response(review) -> ReviewResponse:
    reviewer_name = review.user.username if getattr(review, "user", None) else "Anonymous"
    return ReviewResponse(
        id=review.id,
        film_id=review.film_id,
        reviewer_name=reviewer_name,
        submitted_at=review.created_at,
        rating=review.rating,
        body=review.review_body,
    )


@router.get("/films/{film_id}/reviews", response_model=list[ReviewResponse])
async def get_film_reviews(
    film_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve all reviews for a specific film ordered by newest first (Read-only: all authenticated users).
    Follows: Route -> Handler -> Service -> DAO -> AsyncSession.
    """
    reviews = await review_handler.get_reviews_by_film_id(db, film_id)
    return [_to_review_response(r) for r in reviews]


@router.get("/films/{film_id}/average-rating")
async def get_film_average_rating(
    film_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Get the calculated average rating across all reviews for a film (Read-only: all authenticated users).
    Follows: Route -> Handler -> Service -> DAO -> AsyncSession.
    """
    avg_rating = await review_handler.get_average_rating(db, film_id)
    return {
        "film_id": film_id,
        "average_rating": avg_rating,
    }


@router.post("/films/{film_id}/reviews", response_model=ReviewResponse, status_code=201)
async def create_film_review(
    film_id: UUID,
    review: ReviewCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role(UserRole.ADMIN, UserRole.CRITIC)),
):
    """Create a new review for a film (Admins and Critics only)."""
    created_review = await review_handler.create_review(
        session=db,
        film_id=film_id,
        review_data=review,
        current_user_dict=current_user,
    )
    return _to_review_response(created_review)


@router.get("/reviews/{review_id}", response_model=ReviewResponse)
async def get_review(
    review_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve a single review by ID (Read-only: all authenticated users)."""
    review = await review_handler.get_review_by_id(db, review_id)
    return _to_review_response(review)


@router.patch("/reviews/{review_id}", response_model=ReviewResponse)
async def update_review(
    review_id: UUID,
    review: ReviewUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role(UserRole.ADMIN, UserRole.CRITIC)),
):
    """Update rating and/or body of a review (Admins can update any; Critics only their own)."""
    updated = await review_handler.update_review(
        session=db,
        review_id=review_id,
        review_data=review,
        current_user_dict=current_user,
    )
    return _to_review_response(updated)


@router.delete("/reviews/{review_id}", response_model=ReviewDeleteResponse, status_code=200)
async def delete_review(
    review_id: UUID,
    db: AsyncSession = Depends(get_db),
    trace_id: str = Depends(get_trace_id),
    current_user: dict = Depends(require_role(UserRole.ADMIN, UserRole.CRITIC)),
):
    """Delete a review by ID (Admins can delete any; Critics only their own)."""
    await review_handler.delete_review(db, review_id, current_user_dict=current_user)
    return {
        "status": "success",
        "message": f"Review with ID {review_id} was successfully deleted.",
        "review_id": review_id,
        "trace_id": trace_id,
    }
