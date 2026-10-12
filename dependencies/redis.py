from collections.abc import AsyncIterator
from redis.asyncio import Redis

from database.redis import get_redis

__all__ = ["get_redis"]
