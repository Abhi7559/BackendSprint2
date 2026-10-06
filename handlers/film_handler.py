from collections.abc import Sequence
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from models.film import Film
from schemas.film import FilmCreate, FilmUpdate
from services.film_service import film_service


class FilmHandler:
    """
    Handler layer for films.
    Delegates to FilmService. Does not call DAOs directly and does not execute database queries.
    """

    async def get_films(
        self,
        session: AsyncSession,
        genre: str | None = None,
        start_year: int | None = None,
        end_year: int | None = None,
    ) -> Sequence[Film]:
        return await film_service.get_all_films(
            session,
            genre=genre,
            start_year=start_year,
            end_year=end_year,
        )

    async def get_film_by_id(self, session: AsyncSession, film_id: UUID) -> Film:
        return await film_service.get_film_by_id(session, film_id)

    async def create_film(self, session: AsyncSession, film_data: FilmCreate) -> Film:
        return await film_service.create_film(session, film_data)

    async def update_film(self, session: AsyncSession, film_id: UUID, film_data: FilmUpdate) -> Film:
        return await film_service.update_film(session, film_id, film_data)

    async def delete_film(self, session: AsyncSession, film_id: UUID) -> bool:
        return await film_service.delete_film(session, film_id)


film_handler = FilmHandler()
