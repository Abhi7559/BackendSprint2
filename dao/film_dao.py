from __future__ import annotations

import base64
import uuid
from collections.abc import Sequence
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.film import Film
from schemas.film import FilmCreate, FilmUpdate
from schemas.pagination import FilmFilterParams, PaginationParams


class FilmDAO:
    """
    Data Access Object for Film entity.
    Encapsulates all direct database queries for Film using SQLAlchemy 2.0 async syntax.
    """

    async def list_paginated(
        self,
        session: AsyncSession,
        filters: FilmFilterParams,
        pagination: PaginationParams,
    ) -> tuple[Sequence[Film], int]:
        """
        Dynamically applies filters and fetches only the requested page of films.
        - genre: exact match
        - from_year / to_year: release year bounds
        - director: case-insensitive substring match
        Returns a tuple of (films_for_page, total_count).
        The query never fetches all records from the database.
        """
        # Base query excluding soft-deleted films
        stmt = select(Film).where(Film.is_deleted == False)  # noqa: E712

        # Dynamic filter conditions built at runtime in SQLAlchemy 2.0
        if filters.genre:
            stmt = stmt.where(Film.genre == filters.genre)
        if filters.from_year is not None:
            stmt = stmt.where(Film.release_year >= filters.from_year)
        if filters.to_year is not None:
            stmt = stmt.where(Film.release_year <= filters.to_year)
        if filters.director:
            stmt = stmt.where(Film.director.ilike(f"%{filters.director.strip()}%"))

        # Compute total count of matching records without fetching all rows
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await session.execute(count_stmt)
        total = total_result.scalar() or 0

        # Apply deterministic sorting, OFFSET, and LIMIT to fetch ONLY the requested page
        stmt = (
            stmt.order_by(Film.release_year.desc(), Film.title.asc(), Film.id.asc())
            .offset(pagination.offset)
            .limit(pagination.page_size)
        )

        result = await session.execute(stmt)
        films = result.scalars().all()
        return films, total

    async def list_by_cursor(
        self,
        session: AsyncSession,
        cursor: str | None = None,
        limit: int = 10,
        genre: str | None = None,
    ) -> tuple[Sequence[Film], str | None]:
        """
        Cursor-based pagination mode.
        Uses an opaque base64-encoded cursor representing the last record's ID.
        Fetches limit + 1 items to determine if a next page exists without extra count queries.
        """
        stmt = select(Film).where(Film.is_deleted == False)  # noqa: E712

        if genre:
            stmt = stmt.where(Film.genre == genre)

        # Decode opaque cursor if provided
        if cursor:
            try:
                decoded_id_str = base64.urlsafe_b64decode(cursor.encode()).decode()
                cursor_uuid = uuid.UUID(decoded_id_str)
                stmt = stmt.where(Film.id > cursor_uuid)
            except Exception:
                pass  # Fallback to beginning if invalid cursor

        # Order by unique id ascending and fetch limit + 1 to detect next page
        stmt = stmt.order_by(Film.id.asc()).limit(limit + 1)
        result = await session.execute(stmt)
        records = list(result.scalars().all())

        next_cursor = None
        if len(records) > limit:
            items = records[:limit]
            last_item_id = str(items[-1].id)
            next_cursor = base64.urlsafe_b64encode(last_item_id.encode()).decode()
        else:
            items = records

        return items, next_cursor

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

    async def search(
        self,
        session: AsyncSession,
        query: str | None = None,
    ) -> Sequence[Film]:
        """
        Search films by title or genre matching query string.
        Excludes soft-deleted films.
        """
        stmt = select(Film).where(Film.is_deleted == False)  # noqa: E712
        if query and query.strip():
            search_term = f"%{query.strip()}%"
            stmt = stmt.where(
                (Film.title.ilike(search_term)) | (Film.genre.ilike(search_term))
            )
        stmt = stmt.order_by(Film.title.asc())
        result = await session.execute(stmt)
        return result.scalars().all()

    async def search_with_avg_ratings(
        self,
        session: AsyncSession,
        query: str | None = None,
    ) -> list[dict]:
        """
        Fetches matching films and their average review ratings in a SINGLE database round trip.
        Fixes the N+1 query problem caused by looping over films and calling average_rating() for each.
        """
        from models.review import Review

        stmt = (
            select(Film, func.avg(Review.rating).label("avg_rating"))
            .outerjoin(Review, Review.film_id == Film.id)
            .where(Film.is_deleted == False)  # noqa: E712
            .group_by(Film.id)
        )

        if query and query.strip():
            search_term = f"%{query.strip()}%"
            stmt = stmt.where(
                (Film.title.ilike(search_term)) | (Film.genre.ilike(search_term))
            )

        stmt = stmt.order_by(Film.title.asc())
        result = await session.execute(stmt)
        rows = result.all()

        return [
            {
                "film": row[0],
                "average_rating": min(float(row[1]), 5.0) if row[1] is not None else None,
            }
            for row in rows
        ]

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

    async def recalculate_review_stats(
        self,
        session: AsyncSession,
        film_id: uuid.UUID,
    ) -> None:
        """
        Background task helper:
        Recomputes the denormalized review_count and average_rating on the Film record
        using aggregate SQL queries without blocking the client response.
        """
        from models.review import Review

        # Compute count and average rating across all reviews for this film
        stmt = (
            select(
                func.count(Review.id).label("count"),
                func.avg(Review.rating).label("avg_rating"),
            )
            .where(Review.film_id == film_id)
        )
        result = await session.execute(stmt)
        row = result.one()
        count = row.count or 0
        avg_rating = min(float(row.avg_rating), 5.0) if row.avg_rating is not None else None

        # Update the film record
        film = await self.get_by_id(session, film_id)
        if film:
            film.review_count = count
            film.average_rating = avg_rating
            await session.commit()
            await session.refresh(film)

    async def delete(self, session: AsyncSession, film_id: uuid.UUID) -> bool:
        """
        Delete a film by ID using soft delete (marking is_deleted=True).
        """
        return await self.soft_delete(session, film_id)


# Global DAO instance
film_dao = FilmDAO()
