from uuid import UUID
from fastapi import APIRouter, Depends
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

router = APIRouter(
    prefix="/films",
    tags=["Films"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=FilmListResponse)
async def get_films(
    genre: str | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
    config: Settings = Depends(get_config),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    trace_id: str = Depends(get_trace_id),
):
    """
    Retrieve all films with optional genre and year-range filters.
    Read-through cache powered by Redis with DB fallback.
    """
    films = await film_handler.get_films(
        db,
        redis=redis,
        genre=genre,
        start_year=start_year,
        end_year=end_year,
    )
    return {
        "status": "success",
        "trace_id": trace_id,
        "total": len(films),
        "data": films,
    }


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
