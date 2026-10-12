from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User
from schemas.user import LoginRequest, RegisterRequest
from services.user_service import user_service


class UserHandler:
    async def register_user(self, session: AsyncSession, request: RegisterRequest) -> User:
        return await user_service.register_user(session, request)

    async def login_user(self, session: AsyncSession, request: LoginRequest, redis: Redis | None = None):
        return await user_service.login_user(session, request, redis=redis)

    async def refresh_tokens(self, refresh_token: str, redis: Redis | None = None):
        return await user_service.refresh_tokens(refresh_token, redis=redis)

    async def logout_user(self, user_id: str, redis: Redis | None = None) -> dict:
        return await user_service.logout_user(user_id, redis=redis)

    async def get_or_create_current_user(self, session: AsyncSession, current_user_dict: dict) -> User:
        return await user_service.get_or_create_current_user(session, current_user_dict)

    async def get_admin_stats(self, session: AsyncSession) -> dict:
        return await user_service.get_admin_stats(session)


user_handler = UserHandler()
