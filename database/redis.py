import logging
from collections.abc import AsyncIterator
from redis.asyncio import ConnectionPool, Redis

from core.config import settings

logger = logging.getLogger(__name__)

# Module-level connection pool and client instances
_redis_pool: ConnectionPool | None = None
_redis_client: Redis | None = None


async def init_redis() -> Redis:
    """
    Initializes a shared Redis connection pool and client.
    Called once during application startup.
    """
    global _redis_pool, _redis_client
    if _redis_client is None:
        logger.info(f"Connecting to Redis at {settings.REDIS_URL}")
        _redis_pool = ConnectionPool.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            max_connections=20,
        )
        _redis_client = Redis(connection_pool=_redis_pool)
    return _redis_client


async def close_redis() -> None:
    """
    Gracefully closes Redis connection pool on application shutdown.
    """
    global _redis_pool, _redis_client
    if _redis_client is not None:
        logger.info("Closing Redis connection pool")
        await _redis_client.close()
        _redis_client = None
    if _redis_pool is not None:
        await _redis_pool.disconnect()
        _redis_pool = None


async def get_redis() -> AsyncIterator[Redis]:
    """
    FastAPI dependency providing the shared Redis client.
    Does NOT open or close a new connection per request.
    """
    global _redis_client
    if _redis_client is None:
        await init_redis()
    yield _redis_client
