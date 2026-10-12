from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies.auth import get_current_user, require_role, security_bearer
from dependencies.database import get_db
from dependencies.redis import get_redis
from exceptions.domain import UserRole
from handlers.user_handler import user_handler
from schemas.user import (
    AccessTokenResponse,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(
    tags=["Auth / Users"],
)


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """Register a new user in PostgreSQL with bcrypt hashed password."""
    return await user_handler.register_user(db, request)


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    """Validate credentials, issue access + refresh tokens, and store refresh token in Redis."""
    return await user_handler.login_user(db, request, redis=redis)


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(
    auth_creds: HTTPAuthorizationCredentials | None = Depends(security_bearer),
    redis: Redis = Depends(get_redis),
):
    """Validate refresh token from Authorization Bearer header and Redis, then issue new access token."""
    if not auth_creds or not auth_creds.credentials:
        from exceptions.domain import InvalidTokenError
        raise InvalidTokenError("Authorization Bearer refresh token is missing.")
    return await user_handler.refresh_tokens(auth_creds.credentials, redis=redis)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    current_user: dict = Depends(get_current_user),
    redis: Redis = Depends(get_redis),
):
    """
    Accepts a valid access token, removes the caller's refresh token from Redis,
    and returns a success response.
    Subsequent attempts to use the revoked refresh token will be rejected.
    """
    user_id = str(current_user["user_id"])
    return await user_handler.logout_user(user_id, redis=redis)


@router.get("/users/me", response_model=UserResponse)
async def get_me(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get profile of current logged-in user."""
    return await user_handler.get_or_create_current_user(db, current_user)


@router.get("/admin/stats")
async def get_admin_stats(
    db: AsyncSession = Depends(get_db),
    admin_user: dict = Depends(require_role(UserRole.ADMIN)),
):
    """Get live counts of users and reviews from PostgreSQL (restricted to admin role)."""
    return await user_handler.get_admin_stats(db)
