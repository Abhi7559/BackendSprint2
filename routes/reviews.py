from math import ceil
from uuid import UUID
from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies.auth import get_current_user, require_role
from dependencies.database import get_db
from dependencies.trace import get_trace_id
from exceptions.domain import UserRole
from handlers.review_handler import review_handler
from schemas.pagination import PaginatedResponse, PaginationParams, ReviewFilterParams
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


@router.get("/films/{film_id}/reviews", response_model=PaginatedResponse[ReviewResponse])
async def get_film_reviews(
    film_id: UUID,
    filters: ReviewFilterParams = Depends(),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve paginated reviews for a specific film with optional rating filters:
    - min_rating: minimum review rating (1-5)
    - max_rating: maximum review rating (1-5)
    Eliminates N+1 queries using joinedload to fetch user reviewer details in a single query.
    """
    reviews, total = await review_handler.get_reviews_paginated(
        session=db,
        film_id=film_id,
        filters=filters,
        pagination=pagination,
    )
    total_pages = ceil(total / pagination.page_size) if total > 0 else 0

    return PaginatedResponse(
        items=[_to_review_response(r) for r in reviews],
        page=pagination.page,
        page_size=pagination.page_size,
        total=total,
        total_pages=total_pages,
    )


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


async def _recalculate_film_stats_bg(film_id: UUID) -> None:
    """Background task function to recompute review count & average rating without blocking response."""
    from database.engine import get_session_factory
    from dao.film_dao import film_dao
    session_factory = get_session_factory()
    async with session_factory() as bg_session:
        await film_dao.recalculate_review_stats(bg_session, film_id)


@router.post("/films/{film_id}/reviews", response_model=ReviewResponse, status_code=201)
async def create_film_review(
    film_id: UUID,
    review: ReviewCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role(UserRole.ADMIN, UserRole.CRITIC)),
):
    """
    Create a new review for a film (Admins and Critics only).
    Schedules a background task using FastAPI BackgroundTasks to recompute the denormalized
    review_count and average_rating on the Film record without blocking the client response.
    """
    created_review = await review_handler.create_review(
        session=db,
        film_id=film_id,
        review_data=review,
        current_user_dict=current_user,
    )
    # Schedule background recalculation
    background_tasks.add_task(_recalculate_film_stats_bg, film_id)
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
    background_tasks: BackgroundTasks,
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
    # Recalculate denormalized review stats in the background
    background_tasks.add_task(_recalculate_film_stats_bg, updated.film_id)
    return _to_review_response(updated)


@router.delete("/reviews/{review_id}", response_model=ReviewDeleteResponse, status_code=200)
async def delete_review(
    review_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    trace_id: str = Depends(get_trace_id),
    current_user: dict = Depends(require_role(UserRole.ADMIN, UserRole.CRITIC)),
):
    """Delete a review by ID (Admins can delete any; Critics only their own)."""
    # Fetch review before deleting to know which film to update
    review_obj = await review_handler.get_review_by_id(db, review_id)
    film_id = review_obj.film_id if review_obj else None

    await review_handler.delete_review(db, review_id, current_user_dict=current_user)

    if film_id:
        background_tasks.add_task(_recalculate_film_stats_bg, film_id)

    return {
        "status": "success",
        "message": f"Review with ID {review_id} was successfully deleted.",
        "review_id": review_id,
        "trace_id": trace_id,
    }
