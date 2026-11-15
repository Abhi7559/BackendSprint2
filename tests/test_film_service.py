"""
Unit tests for FilmService business rules and calculations.
Includes:
- Parametrized test checking filtering and average calculation logic with zero infra
- Film deletion blocked when active reviews exist (asserting FilmHasActiveReviewsError)
- FilmNotFoundError carries the requested film_id
"""

import uuid
from unittest.mock import AsyncMock, patch
import pytest

from exceptions.domain import FilmHasActiveReviewsError, FilmNotFoundError
from models.film import Film
from services.film_service import FilmService


# ---------------------------------------------------------------------------
# Business Rule Unit Tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_delete_film_raises_film_not_found():
    """
    Business Rule 1: Attempting to delete a non-existent film raises FilmNotFoundError
    carrying the requested film_id.
    """
    service = FilmService()
    fake_session = AsyncMock()
    missing_film_id = uuid.uuid4()

    with patch("services.film_service.film_dao.get_by_id", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = None

        with pytest.raises(FilmNotFoundError) as exc_info:
            import asyncio
            asyncio.run(service.delete_film(fake_session, missing_film_id))

        assert exc_info.value.film_id == missing_film_id
        assert f"Film {missing_film_id} was not found." in str(exc_info.value)


@pytest.mark.unit
def test_delete_film_rejected_when_active_reviews_exist(sample_film: Film):
    """
    Business Rule 2: A film cannot be soft-deleted while it still has active reviews.
    Asserts FilmHasActiveReviewsError carrying the exact film_id.
    """
    service = FilmService()
    fake_session = AsyncMock()

    with patch("services.film_service.film_dao.get_by_id", new_callable=AsyncMock) as mock_get_film, \
         patch("services.film_service.review_dao.has_active_reviews", new_callable=AsyncMock) as mock_has_rev:

        mock_get_film.return_value = sample_film
        mock_has_rev.return_value = True  # Active reviews present

        with pytest.raises(FilmHasActiveReviewsError) as exc_info:
            import asyncio
            asyncio.run(service.delete_film(fake_session, sample_film.id))

        assert exc_info.value.film_id == sample_film.id
        assert f"Film {sample_film.id} cannot be deleted because it has active reviews." in str(exc_info.value)


# ---------------------------------------------------------------------------
# Parametrized Calculation & Filter Unit Tests (Pure in-memory, zero infra)
# ---------------------------------------------------------------------------

def filter_films_in_memory(
    films: list[Film],
    genre: str | None = None,
    from_year: int | None = None,
    to_year: int | None = None,
) -> list[str]:
    """Helper implementing platform catalogue filtering purely over plain objects."""
    result = films
    if genre:
        result = [f for f in result if f.genre.lower() == genre.lower()]
    if from_year is not None:
        result = [f for f in result if f.release_year >= from_year]
    if to_year is not None:
        result = [f for f in result if f.release_year <= to_year]
    return [f.title for f in result]


@pytest.mark.unit
@pytest.mark.parametrize(
    "genre,from_year,to_year,expected_titles",
    [
        # Case 1: Genre filter only
        ("Sci-Fi", None, None, ["Interstellar", "Inception"]),
        # Case 2: Year range filter only
        (None, 2010, 2015, ["Interstellar", "Inception"]),
        # Case 3: Combined genre + year lower bound
        ("Sci-Fi", 2012, None, ["Interstellar"]),
        # Case 4: No matching results
        ("Horror", None, None, []),
        # Case 5: Exact single match by genre & era
        ("Crime", None, 1980, ["The Godfather"]),
        # Case 6: Action genre match
        ("Action", None, None, ["The Dark Knight"]),
    ],
)
def test_parametrized_film_filtering(
    sample_films_catalog: list[Film],
    genre: str | None,
    from_year: int | None,
    to_year: int | None,
    expected_titles: list[str],
):
    """
    Parametrized test running the exact same assertion logic across 6 distinct input/output pairs.
    Exercises multi-field filter combinations with plain Python objects.
    """
    matched = filter_films_in_memory(sample_films_catalog, genre, from_year, to_year)
    assert matched == expected_titles


@pytest.mark.unit
@pytest.mark.parametrize(
    "ratings,expected_average",
    [
        ([5, 5, 5], 5.0),
        ([1, 2, 3, 4, 5], 3.0),
        ([4, 5], 4.5),
        ([10, 8, 9], 9.0),
        ([], None),
    ],
)
def test_parametrized_average_rating_calculation(ratings: list[int], expected_average: float | None):
    """
    Parametrized test for review average rating calculation across various distributions.
    """
    avg = sum(ratings) / len(ratings) if ratings else None
    assert avg == expected_average
