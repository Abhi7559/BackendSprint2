"""
Shared test configuration and typed fixtures for Film Review Platform unit tests.
Zero running infrastructure required: operates purely on in-memory objects.
"""

import uuid
from datetime import datetime, timezone
import pytest

from models.film import Film
from models.user import User
from models.review import Review


# ---------------------------------------------------------------------------
# Film Fixtures (Function-scoped for isolation)
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_film() -> Film:
    """Fixture providing a standard in-memory Film instance."""
    return Film(
        id=uuid.uuid4(),
        title="Interstellar",
        release_year=2014,
        genre="Sci-Fi",
        director="Christopher Nolan",
        is_deleted=False,
        review_count=1,
        average_rating=9.0,
    )


@pytest.fixture
def sample_films_catalog() -> list[Film]:
    """Fixture providing a list of varied film instances for filtering tests."""
    return [
        Film(
            id=uuid.uuid4(),
            title="Interstellar",
            release_year=2014,
            genre="Sci-Fi",
            director="Christopher Nolan",
            is_deleted=False,
        ),
        Film(
            id=uuid.uuid4(),
            title="Inception",
            release_year=2010,
            genre="Sci-Fi",
            director="Christopher Nolan",
            is_deleted=False,
        ),
        Film(
            id=uuid.uuid4(),
            title="The Godfather",
            release_year=1972,
            genre="Crime",
            director="Francis Ford Coppola",
            is_deleted=False,
        ),
        Film(
            id=uuid.uuid4(),
            title="The Dark Knight",
            release_year=2008,
            genre="Action",
            director="Christopher Nolan",
            is_deleted=False,
        ),
        Film(
            id=uuid.uuid4(),
            title="Parasite",
            release_year=2019,
            genre="Drama",
            director="Bong Joon-ho",
            is_deleted=False,
        ),
    ]


# ---------------------------------------------------------------------------
# User Fixtures (Across all 3 roles: admin, critic, viewer)
# ---------------------------------------------------------------------------

@pytest.fixture
def admin_user() -> User:
    """Fixture providing an admin user instance."""
    return User(
        id=uuid.uuid4(),
        username="admin_sarah",
        email="admin@example.com",
        role="admin",
        password_hash="hashed_pw_1",
    )


@pytest.fixture
def critic_user() -> User:
    """Fixture providing a critic/reviewer user instance."""
    return User(
        id=uuid.uuid4(),
        username="critic_marcus",
        email="marcus@example.com",
        role="critic",
        password_hash="hashed_pw_2",
    )


@pytest.fixture
def viewer_user() -> User:
    """Fixture providing a standard member/viewer user instance."""
    return User(
        id=uuid.uuid4(),
        username="viewer_elena",
        email="elena@example.com",
        role="viewer",
        password_hash="hashed_pw_3",
    )


# ---------------------------------------------------------------------------
# Review Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_review(sample_film: Film, critic_user: User) -> Review:
    """Fixture providing a review instance linked to sample_film and critic_user."""
    return Review(
        id=uuid.uuid4(),
        film_id=sample_film.id,
        user_id=critic_user.id,
        rating=9,
        review_body="A breathtaking visual and emotional odyssey through space and time.",
        created_at=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# Async Database & HTTP Integration Fixtures (aiosqlite in-memory)
# ---------------------------------------------------------------------------
from collections.abc import AsyncGenerator
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from database.base import Base
from dependencies.database import get_db
from dependencies.redis import get_redis
from main import app

from sqlalchemy.pool import StaticPool

# Isolated in-memory async SQLite engine for integration tests
TEST_DB_URL = "sqlite+aiosqlite:///file:testdb?mode=memory&cache=shared&uri=true"

test_engine = create_async_engine(
    TEST_DB_URL,
    echo=False,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest.fixture(scope="session", autouse=True)
async def prepare_test_database():
    """Create all database tables once for the test session and clean up after."""
    import models  # noqa: F401 - ensure all ORM models are registered with Base.metadata
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Transaction-rollback fixture ensuring every test starts from a clean state.
    Opens a connection, starts an outer transaction, yields the session,
    and rolls back when the test completes.
    """
    connection = await test_engine.connect()
    transaction = await connection.begin()
    session = AsyncSession(bind=connection, expire_on_commit=False)

    yield session

    await session.close()
    await transaction.rollback()
    await connection.close()


class FakeRedis:
    """Simple in-memory fake for Redis so integration tests run without live Redis."""
    def __init__(self):
        self.store = {}

    async def get(self, key: str):
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None):
        self.store[key] = value

    async def delete(self, *keys: str):
        for k in keys:
            self.store.pop(k, None)

    async def scan(self, cursor: int = 0, match: str | None = None):
        """Simulate redis scan."""
        import fnmatch
        keys = list(self.store.keys())
        if match:
            matched = [k for k in keys if fnmatch.fnmatch(k, match)]
        else:
            matched = keys
        return 0, matched


fake_redis_instance = FakeRedis()


@pytest.fixture
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Test HTTP client fixture configured with FastAPI dependency overrides.
    Overrides get_db to return our isolated test session and get_redis with a fake.
    """
    from database.engine import set_session_factory, SessionLocal

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    async def override_get_redis():
        yield fake_redis_instance

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis
    set_session_factory(TestingSessionLocal)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
    set_session_factory(SessionLocal)


