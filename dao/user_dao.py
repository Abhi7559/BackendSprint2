import uuid
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User


class UserDAO:
    """
    Data Access Object for User entity.
    Encapsulates all direct database queries for User using SQLAlchemy 2.0 async syntax.
    """

    async def get_by_id(self, session: AsyncSession, user_id: uuid.UUID) -> User | None:
        """Fetch a single user by ID."""
        stmt = select(User).where(User.id == user_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_username(self, session: AsyncSession, username: str) -> User | None:
        """Fetch a single user by username."""
        stmt = select(User).where(User.username == username)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, session: AsyncSession, email: str) -> User | None:
        """
        Fetch a single user by email address.
        Returns None when not found.
        Used for authentication and duplicate checks.
        """
        stmt = select(User).where(User.email == email)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, session: AsyncSession, username: str, email: str, role: str = "user") -> User:
        """Create a new user record in the database."""
        user = User(username=username, email=email, role=role)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user

    async def count_users(self, session: AsyncSession) -> int:
        """Count total users in the system."""
        stmt = select(func.count(User.id))
        result = await session.execute(stmt)
        return result.scalar() or 0


# Global DAO instance
user_dao = UserDAO()
