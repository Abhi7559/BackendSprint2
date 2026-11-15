from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.config import settings

# Create the async engine using the database connection URL from settings
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)

# Async sessionmaker factory
SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

_session_factory = SessionLocal


def get_session_factory():
    """Return the active async session factory (can be swapped in tests)."""
    return _session_factory


def set_session_factory(factory):
    """Override the active async session factory."""
    global _session_factory
    _session_factory = factory

