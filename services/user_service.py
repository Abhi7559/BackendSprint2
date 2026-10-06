from sqlalchemy.ext.asyncio import AsyncSession

from dao.review_dao import review_dao
from dao.user_dao import user_dao
from exceptions.domain import EmailAlreadyExistsError, InvalidCredentialsError
from models.user import User
from schemas.user import LoginRequest, RegisterRequest


class UserService:
    """
    Service layer for users.
    Delegates all queries to UserDAO and ReviewDAO instead of direct session.execute.
    """

    async def register_user(self, session: AsyncSession, request: RegisterRequest) -> User:
        existing_user = await user_dao.get_by_email(session, request.email)
        if existing_user:
            raise EmailAlreadyExistsError(request.email)

        return await user_dao.create(
            session=session,
            username=request.name.lower().replace(" ", "_"),
            email=request.email,
            role="user",
        )

    async def login_user(self, session: AsyncSession, request: LoginRequest) -> dict:
        user = await user_dao.get_by_email(session, request.email)
        if not user:
            raise InvalidCredentialsError()
        return {
            "message": "User logged in successfully",
            "username": user.username,
            "email": user.email,
            "role": user.role,
        }

    async def get_or_create_current_user(self, session: AsyncSession, current_user_dict: dict) -> User:
        user = await user_dao.get_by_username(session, current_user_dict["username"])
        if not user:
            user = await user_dao.create(
                session=session,
                username=current_user_dict["username"],
                email=f"{current_user_dict['username']}@example.com",
                role=current_user_dict.get("role", "user"),
            )
        return user

    async def get_admin_stats(self, session: AsyncSession) -> dict:
        total_users = await user_dao.count_users(session)
        total_reviews = await review_dao.count_reviews(session)
        return {
            "message": "Admin statistics retrieved successfully",
            "total_users": total_users,
            "total_reviews": total_reviews,
        }


user_service = UserService()
