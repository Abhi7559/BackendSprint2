import json
import logging
from collections.abc import Sequence
from uuid import UUID
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from dao.film_dao import film_dao
from dao.review_dao import review_dao
from exceptions.domain import FilmHasActiveReviewsError, FilmNotFoundError
from models.film import Film
from schemas.film import FilmCreate, FilmResponse, FilmUpdate

logger = logging.getLogger(__name__)


class FilmService:
    """
    Service layer for films.
    Orchestrates business logic, calls FilmDAO and ReviewDAO,
    and manages read-through caching and invalidation in Redis.
    """

    FILM_CACHE_PREFIX = "films:list"

    def _build_cache_key(
        self,
        genre: str | None = None,
        start_year: int | None = None,
        end_year: int | None = None,
    ) -> str:
        """Generate deterministic cache key for film queries."""
        return f"{self.FILM_CACHE_PREFIX}:genre={genre}:start={start_year}:end={end_year}"

    async def invalidate_film_caches(self, redis: Redis | None) -> None:
        """
        Invalidate all cached film list entries matching 'films:list:*'.
        Called on create, update, or soft-delete.
        """
        if not redis:
            return
        try:
            # Use SCAN to find keys with matching pattern
            cursor = 0
            keys_to_delete = []
            while True:
                cursor, keys = await redis.scan(cursor=cursor, match=f"{self.FILM_CACHE_PREFIX}*")
                keys_to_delete.extend(keys)
                if cursor == 0:
                    break

            if keys_to_delete:
                await redis.delete(*keys_to_delete)
                logger.info(f"Invalidated {len(keys_to_delete)} film list cache entries.")
        except Exception as e:
            logger.warning(f"Failed to invalidate film caches in Redis: {e}")

    async def get_all_films(
        self,
        session: AsyncSession,
        redis: Redis | None = None,
        genre: str | None = None,
        start_year: int | None = None,
        end_year: int | None = None,
    ) -> list[dict]:
        """
        Read-through caching pattern:
        1. Check Redis for cached serialized film list
        2. On cache hit, return immediately
        3. On cache miss, fetch from PostgreSQL, serialize, store in Redis with TTL, and return
        """
        cache_key = self._build_cache_key(genre, start_year, end_year)

        # 1. Check Redis
        if redis is not None:
            try:
                cached_data = await redis.get(cache_key)
                if cached_data:
                    logger.info(f"Cache HIT for key: {cache_key}")
                    return json.loads(cached_data)
            except Exception as e:
                logger.warning(f"Redis cache lookup error: {e}")

        # 2. On miss: fetch from PostgreSQL
        logger.info(f"Cache MISS for key: {cache_key}. Fetching from PostgreSQL.")
        films = await film_dao.list(
            session,
            genre=genre,
            start_year=start_year,
            end_year=end_year,
        )

        # 3. Serialize data
        serialized = [
            FilmResponse.model_validate(f).model_dump(mode="json")
            for f in films
        ]

        # 4. Write back to Redis with TTL
        if redis is not None:
            try:
                await redis.set(
                    cache_key,
                    json.dumps(serialized),
                    ex=settings.FILM_LIST_CACHE_TTL_SECONDS,
                )
                logger.info(f"Stored film list in cache with TTL {settings.FILM_LIST_CACHE_TTL_SECONDS}s")
            except Exception as e:
                logger.warning(f"Failed to store film list in Redis: {e}")

        return serialized

    async def get_film_by_id(self, session: AsyncSession, film_id: UUID) -> Film:
        film = await film_dao.get_by_id(session, film_id)
        if not film:
            raise FilmNotFoundError(film_id=film_id)
        return film

    async def create_film(
        self,
        session: AsyncSession,
        film_data: FilmCreate,
        redis: Redis | None = None,
    ) -> Film:
        film = await film_dao.create(session, film_data)
        logger.info(f"Film created successfully with id {film.id}.")
        await self.invalidate_film_caches(redis)
        return film

    async def update_film(
        self,
        session: AsyncSession,
        film_id: UUID,
        film_data: FilmUpdate,
        redis: Redis | None = None,
    ) -> Film:
        film = await film_dao.get_by_id(session, film_id)
        if not film:
            raise FilmNotFoundError(film_id=film_id)

        updated = await film_dao.update(session, film_id, film_data)
        if not updated:
            raise FilmNotFoundError(film_id=film_id)

        logger.info(f"Film {film_id} updated successfully.")
        await self.invalidate_film_caches(redis)
        return updated

    async def delete_film(
        self,
        session: AsyncSession,
        film_id: UUID,
        redis: Redis | None = None,
    ) -> bool:
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
        await self.invalidate_film_caches(redis)
        return True


film_service = FilmService()
