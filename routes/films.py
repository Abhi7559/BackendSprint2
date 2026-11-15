from math import ceil
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import Settings
from dependencies.auth import get_current_user, require_role
from dependencies.config import get_config
from dependencies.database import get_db
from dependencies.redis import get_redis
from dependencies.trace import get_trace_id
from exceptions.domain import UserRole
from handlers.film_handler import film_handler
from schemas.film import (
    FilmCreate,
    FilmDeleteResponse,
    FilmListResponse,
    FilmResponse,
    FilmUpdate,
    ReleaseWindow,
)
from schemas.pagination import (
    CursorPageResponse,
    FilmFilterParams,
    PaginatedResponse,
    PaginationParams,
)

router = APIRouter(
    prefix="/films",
    tags=["Films"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=PaginatedResponse[FilmResponse])
async def get_films(
    filters: FilmFilterParams = Depends(),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    trace_id: str = Depends(get_trace_id),
):
    """
    Retrieve films with offset-based pagination and multi-field filters:
    - genre: exact match
    - from_year / to_year: release year range (individually optional)
    - director: case-insensitive substring match
    The underlying database query only fetches the requested page of records.
    """
    films, total = await film_handler.get_films_paginated(db, filters, pagination)
    total_pages = ceil(total / pagination.page_size) if total > 0 else 0

    return PaginatedResponse(
        items=films,
        page=pagination.page,
        page_size=pagination.page_size,
        total=total,
        total_pages=total_pages,
    )


@router.get("/cursor", response_model=CursorPageResponse[FilmResponse])
async def get_films_cursor(
    cursor: str | None = Query(default=None, description="Opaque next_cursor token returned from previous page"),
    limit: int = Query(default=10, ge=1, le=100, description="Items per batch"),
    genre: str | None = Query(default=None, description="Optional exact genre filter"),
    db: AsyncSession = Depends(get_db),
    trace_id: str = Depends(get_trace_id),
):
    """
    Retrieve films using cursor-based pagination as an alternative mode.
    Returns next_cursor (null when no further pages exist) which is opaque to the client.
    """
    items, next_cursor = await film_handler.get_films_by_cursor(db, cursor=cursor, limit=limit, genre=genre)
    return CursorPageResponse(
        items=items,
        next_cursor=next_cursor,
    )


@router.get("/{film_id}", response_model=FilmResponse)
async def get_film(
    film_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve a film by ID.
    Follows: Route -> Handler -> Service -> DAO -> AsyncSession.
    """
    return await film_handler.get_film_by_id(db, film_id)


@router.post("", response_model=FilmResponse, status_code=201)
async def create_film(
    film: FilmCreate,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    admin_user: dict = Depends(require_role(UserRole.ADMIN)),
):
    """Create a new film record and invalidate film list cache (Admin only)."""
    return await film_handler.create_film(db, film, redis=redis)


@router.patch("/{film_id}", response_model=FilmResponse)
async def update_film(
    film_id: UUID,
    film: FilmUpdate,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    admin_user: dict = Depends(require_role(UserRole.ADMIN)),
):
    """Update an existing film and invalidate film list cache (Admin only)."""
    return await film_handler.update_film(db, film_id, film, redis=redis)


@router.delete("/{film_id}", response_model=FilmDeleteResponse, status_code=200)
async def delete_film(
    film_id: UUID,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    trace_id: str = Depends(get_trace_id),
    admin_user: dict = Depends(require_role(UserRole.ADMIN)),
):
    """Delete a film by ID and invalidate film list cache (Admin only)."""
    await film_handler.delete_film(db, film_id, redis=redis)
    return {
        "status": "success",
        "message": f"Film with ID {film_id} was successfully deleted.",
        "film_id": film_id,
        "trace_id": trace_id,
    }



@router.post("/filter-by-window")
def filter_films_by_window(window: ReleaseWindow):
    """
    Filter films within a release year window.
    Demonstrates ReleaseWindow cross-field validation in Swagger UI.
    """
    return {
        "message": f"Filtering films between {window.start_year} and {window.end_year}",
        "start_year": window.start_year,
        "end_year": window.end_year,
    }
