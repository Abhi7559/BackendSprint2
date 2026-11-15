from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from core.config import settings

_engine: AsyncEngine | None = None
_session_factory = None


def get_engine() -> AsyncEngine:
    """Lazily initialize and return the SQLAlchemy AsyncEngine using settings.DATABASE_URL."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.DATABASE_URL,
            echo=False,
            pool_pre_ping=True,
        )
    return _engine


# Proxy for backward compatibility with code importing `engine` directly
class _EngineProxy:
    def __getattr__(self, name):
        return getattr(get_engine(), name)


engine = _EngineProxy()


def SessionLocal():
    """Async sessionmaker factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    return _session_factory()


def get_session_factory():
    """Return the active async session factory (can be swapped in tests)."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    return _session_factory


def set_session_factory(factory):
    """Override the active async session factory."""
    global _session_factory
    _session_factory = factory
