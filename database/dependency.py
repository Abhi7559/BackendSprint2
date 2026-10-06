from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession

from database.engine import SessionLocal


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Request-scoped AsyncSession dependency.
    Yields an AsyncSession per request and guarantees session closure when the request ends.
    """
    async with SessionLocal() as session:
        yield session
