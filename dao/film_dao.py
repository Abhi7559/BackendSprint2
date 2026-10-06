import uuid
from collections.abc import Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.film import Film
from schemas.film import FilmCreate, FilmUpdate


class FilmDAO:
    """
    Data Access Object for Film entity.
    Encapsulates all direct database queries for Film using SQLAlchemy 2.0 async syntax.
    """

    async def get_by_id(self, session: AsyncSession, film_id: uuid.UUID) -> Film | None:
        """
        Fetch a single non-deleted film by ID.
        Returns None when not found instead of raising an exception.
        """
        stmt = select(Film).where(Film.id == film_id, Film.is_deleted == False)  # noqa: E712
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def list(
        self,
        session: AsyncSession,
        genre: str | None = None,
        start_year: int | None = None,
        end_year: int | None = None,
    ) -> Sequence[Film]:
        """
        List films with optional genre and year-range filters.
        Filters are applied only when provided (not None).
        Excludes soft-deleted films (is_deleted == False).
        """
        stmt = select(Film).where(Film.is_deleted == False)  # noqa: E712

        if genre is not None:
            stmt = stmt.where(Film.genre.ilike(f"%{genre}%"))

        if start_year is not None:
            stmt = stmt.where(Film.release_year >= start_year)

        if end_year is not None:
            stmt = stmt.where(Film.release_year <= end_year)

        result = await session.execute(stmt)
        return result.scalars().all()

    # Alias for backward-compatibility with existing calls
    async def get_all(
        self,
        session: AsyncSession,
        genre: str | None = None,
        start_year: int | None = None,
        end_year: int | None = None,
    ) -> Sequence[Film]:
        return await self.list(
            session,
            genre=genre,
            start_year=start_year,
            end_year=end_year,
        )

    async def create(self, session: AsyncSession, film: Film | FilmCreate) -> Film:
        """
        Create a new film record.
        Accepts either an ORM Film model instance or FilmCreate schema.
        """
        if isinstance(film, Film):
            film_record = film
        else:
            film_record = Film(
                title=film.title,
                release_year=film.release_year,
                genre=film.genre,
                director=film.director,
            )
        session.add(film_record)
        await session.commit()
        await session.refresh(film_record)
        return film_record

    async def update(
        self,
        session: AsyncSession,
        film_id: uuid.UUID,
        data: FilmUpdate,
    ) -> Film | None:
        """
        Update an existing film.
        Only updates fields that were explicitly provided (exclude_unset=True).
        Returns None if the film does not exist.
        """
        film = await self.get_by_id(session, film_id)
        if not film:
            return None

        update_dict = data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(film, key, value)

        await session.commit()
        await session.refresh(film)
        return film

    async def soft_delete(self, session: AsyncSession, film_id: uuid.UUID) -> bool:
        """
        Soft-delete a film by marking it inactive/deleted (is_deleted=True)
        without removing the row from the database.
        Returns True when found and marked deleted, False when not found.
        """
        film = await self.get_by_id(session, film_id)
        if not film:
            return False

        film.is_deleted = True
        await session.commit()
        return True

    async def delete(self, session: AsyncSession, film_id: uuid.UUID) -> bool:
        """
        Delete a film by ID using soft delete (marking is_deleted=True).
        """
        return await self.soft_delete(session, film_id)


# Global DAO instance
film_dao = FilmDAO()
