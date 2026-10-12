import uuid
from typing import Any
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from core.security import decode_token
from exceptions.domain import InvalidTokenError

# HTTPBearer security scheme registers the "Authorize" button and lock symbol in Swagger UI
security_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    auth_creds: HTTPAuthorizationCredentials | None = Depends(security_bearer),
) -> dict[str, Any]:
    """
    Reusable FastAPI dependency that extracts and validates the JWT access token
    using HTTPBearer (which adds the lock icon in Swagger docs).
    Automatically rejects unauthenticated or expired callers with 401.
    Does not query PostgreSQL on every request.
    """
    if not auth_creds or not auth_creds.credentials:
        raise InvalidTokenError("Authorization credentials missing or invalid.")

    token = auth_creds.credentials.strip()

    try:
        payload = decode_token(token.strip())
    except JWTError:
        raise InvalidTokenError("Token is invalid or expired.")

    if payload.get("type") != "access":
        raise InvalidTokenError("Token is not an access token.")

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise InvalidTokenError("Token payload missing user identifier.")

    try:
        user_uuid = uuid.UUID(user_id_str)
    except ValueError:
        user_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, user_id_str)

    return {
        "user_id": user_uuid,
        "username": payload.get("username", "user"),
        "email": payload.get("email", ""),
        "role": payload.get("role", "member"),
    }


def require_role(*allowed_roles: str):
    """
    Dependency factory for Role-Based Access Control (RBAC).
    Checks the authenticated user's role and raises 403 Forbidden
    if the caller doesn't have the required role.
    """
    async def role_checker(
        current_user: dict[str, Any] = Depends(get_current_user),
    ) -> dict[str, Any]:
        user_role = current_user.get("role")
        # Allowed roles can be strings or UserRole enum values
        role_strings = [r.value if hasattr(r, "value") else str(r) for r in allowed_roles]
        if user_role not in role_strings:
            from exceptions.domain import ForbiddenError
            raise ForbiddenError(
                f"Role '{user_role}' does not have permission. Allowed roles: {', '.join(role_strings)}."
            )
        return current_user

    return role_checker
