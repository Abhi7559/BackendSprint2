from pathlib import Path
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from dao.film_dao import film_dao
from dao.review_dao import ReviewDAO
from dependencies.database import get_db

review_dao = ReviewDAO()

# Base templates directory path relative to this file
BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Dedicated router for server-rendered HTML views
router = APIRouter(
    prefix="/ui",
    tags=["UI - Server Rendered Views"],
)


@router.get("/films", response_class=HTMLResponse)
async def get_films_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="films.html",
    )


@router.get("/films/search", response_class=HTMLResponse)
async def search_films_fragment(
    request: Request,
    q: str = Query(default="", description="Search query string"),
    db: AsyncSession = Depends(get_db),
):
    """
    Renders an HTML fragment (not a complete page) displaying matching film cards.
    Queries the existing DAO layer and calculates average rating for each film.
    Never returns JSON - always returns an HTML snippet.
    """
    # Single database query with outerjoin and group_by to eliminate N+1 round trips
    films_with_ratings = await film_dao.search_with_avg_ratings(db, query=q)

    return templates.TemplateResponse(
        request=request,
        name="film_cards.html",
        context={"films": films_with_ratings, "query": q},
    )
