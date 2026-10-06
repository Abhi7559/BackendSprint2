from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import Settings
from dependencies.config import get_config
from dependencies.database import get_db
from dependencies.trace import get_trace_id
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
)


@router.get("", response_model=FilmListResponse)
async def get_films(
    genre: str | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
    config: Settings = Depends(get_config),
    db: AsyncSession = Depends(get_db),
    trace_id: str = Depends(get_trace_id),
):
    """
    Retrieve all films with optional genre and year-range filters.
    Follows: Route -> Handler -> Service -> DAO -> AsyncSession.
    """
    films = await film_handler.get_films(
        db,
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
):
    """Create a new film record."""
    return await film_handler.create_film(db, film)


@router.patch("/{film_id}", response_model=FilmResponse)
async def update_film(
    film_id: UUID,
    film: FilmUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update an existing film."""
    return await film_handler.update_film(db, film_id, film)


@router.delete("/{film_id}", response_model=FilmDeleteResponse, status_code=200)
async def delete_film(
    film_id: UUID,
    db: AsyncSession = Depends(get_db),
    trace_id: str = Depends(get_trace_id),
):
    """Delete a film by ID and return confirmation with trace ID."""
    await film_handler.delete_film(db, film_id)
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
