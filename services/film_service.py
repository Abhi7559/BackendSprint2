import logging
from collections.abc import Sequence
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from dao.film_dao import film_dao
from dao.review_dao import review_dao
from exceptions.domain import FilmHasActiveReviewsError, FilmNotFoundError
from models.film import Film
from schemas.film import FilmCreate, FilmUpdate

logger = logging.getLogger(__name__)


class FilmService:
    """
    Service layer for films.
    Orchestrates business logic and calls FilmDAO and ReviewDAO.
    Does not execute direct DB queries.
    """

    async def get_all_films(
        self,
        session: AsyncSession,
        genre: str | None = None,
        start_year: int | None = None,
        end_year: int | None = None,
    ) -> Sequence[Film]:
        return await film_dao.list(
            session,
            genre=genre,
            start_year=start_year,
            end_year=end_year,
        )

    async def get_film_by_id(self, session: AsyncSession, film_id: UUID) -> Film:
        film = await film_dao.get_by_id(session, film_id)
        if not film:
            raise FilmNotFoundError(film_id=film_id)
        return film

    async def create_film(self, session: AsyncSession, film_data: FilmCreate) -> Film:
        film = await film_dao.create(session, film_data)
        logger.info(f"Film created successfully with id {film.id}.")
        return film

    async def update_film(self, session: AsyncSession, film_id: UUID, film_data: FilmUpdate) -> Film:
        film = await film_dao.get_by_id(session, film_id)
        if not film:
            raise FilmNotFoundError(film_id=film_id)

        updated = await film_dao.update(session, film_id, film_data)
        if not updated:
            raise FilmNotFoundError(film_id=film_id)

        logger.info(f"Film {film_id} updated successfully.")
        return updated

    async def delete_film(self, session: AsyncSession, film_id: UUID) -> bool:
        """
        Soft-delete a film.
        Business Rule: A film cannot be soft-deleted while it still has active reviews.
        """
        film = await film_dao.get_by_id(session, film_id)
        if not film:
            raise FilmNotFoundError(film_id=film_id)

        has_active = await review_dao.has_active_reviews(session, film_id)
        if has_active:
            logger.warning(f"Film {film_id} cannot be deleted because active reviews exist.")
            raise FilmHasActiveReviewsError(film_id=film_id)

        await film_dao.soft_delete(session, film_id)
        logger.info(f"Film {film_id} soft-deleted successfully.")
        return True


film_service = FilmService()
