from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings

from core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from dao.review_dao import review_dao
from dao.user_dao import user_dao
from exceptions.domain import (
    EmailAlreadyExistsError,
    InvalidCredentialsError,
    InvalidTokenError,
    UsernameAlreadyExistsError,
    UserRole,
)
from models.user import User
from schemas.user import (
    AccessTokenResponse,
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    TokenResponse,
)


class UserService:
    """
    Service layer for users and authentication.
    Delegates all queries to UserDAO and ReviewDAO.
    """

    async def register_user(self, session: AsyncSession, request: RegisterRequest) -> User:
        """Register a new user with unique username, email, and password hashed using bcrypt."""
        existing_by_username = await user_dao.get_by_username(session, request.username)
        if existing_by_username:
            raise UsernameAlreadyExistsError(request.username)

        existing_user = await user_dao.get_by_email(session, request.email)
        if existing_user:
            raise EmailAlreadyExistsError(request.email)

        # Hash password using Passlib with bcrypt
        hashed_pw = hash_password(request.password)

        # Ensure role is one of the valid enum values
        role_value = request.role.value if isinstance(request.role, UserRole) else str(request.role)

        return await user_dao.create(
            session=session,
            username=request.username,
            email=request.email,
            role=role_value,
            password_hash=hashed_pw,
        )

    async def login_user(
        self,
        session: AsyncSession,
        request: LoginRequest,
        redis: Redis | None = None,
    ) -> TokenResponse:
        """Verify credentials by username only, issue tokens, and store refresh token in Redis with TTL."""
        if not request.username:
            raise InvalidCredentialsError()

        user = await user_dao.get_by_username(session, request.username)
        if not user:
            raise InvalidCredentialsError()

        # Verify submitted password against stored bcrypt password_hash
        if not user.password_hash or not verify_password(request.password, user.password_hash):
            raise InvalidCredentialsError()

        token_data = {
            "sub": str(user.id),
            "username": user.username,
            "email": user.email,
            "role": user.role,
        }
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)

        # Store refresh token in Redis with TTL matching expiry days
        if redis is not None:
            ttl_seconds = settings.TOKEN_REFRESH_TOKEN_EXPIRE_DAYS * 86400
            redis_key = f"refresh_token:{user.id}"
            await redis.set(redis_key, refresh_token, ex=ttl_seconds)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
        )

    async def refresh_tokens(
        self,
        refresh_token: str,
        redis: Redis | None = None,
    ) -> AccessTokenResponse:
        """Validate refresh token against JWT signature and Redis store, then issue new access token."""
        if not refresh_token or not refresh_token.strip():
            raise InvalidTokenError("Refresh token missing or empty.")

        try:
            payload = decode_token(refresh_token.strip())
        except Exception:
            raise InvalidTokenError("Refresh token is invalid or expired.")

        token_type = payload.get("type")
        if token_type not in ("refresh", "access"):
            raise InvalidTokenError("Provided token is invalid.")

        user_id = payload.get("sub")
        if not user_id:
            raise InvalidTokenError("Invalid token payload: missing subject.")

        # Check Redis if refresh token is revoked or expired
        if redis is not None and token_type == "refresh":
            stored_token = await redis.get(f"refresh_token:{user_id}")
            if not stored_token or stored_token != refresh_token.strip():
                raise InvalidTokenError("Refresh token has been revoked or expired.")

        token_data = {
            "sub": user_id,
            "username": payload.get("username"),
            "email": payload.get("email"),
            "role": payload.get("role"),
        }
        new_access_token = create_access_token(token_data)

        return AccessTokenResponse(
            access_token=new_access_token,
            token_type="bearer",
        )

    async def logout_user(
        self,
        user_id: str,
        redis: Redis | None = None,
    ) -> dict:
        """Invalidate the user's refresh token by removing it from Redis."""
        if redis is not None:
            await redis.delete(f"refresh_token:{user_id}")
        return {"message": "Successfully logged out."}

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
