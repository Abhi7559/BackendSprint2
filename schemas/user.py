from pydantic import BaseModel, ConfigDict, EmailStr, Field

from exceptions.domain import UserRole


class UserResponse(BaseModel):
    """
    Public response schema for user profiles.
    - Password and password_hash are intentionally omitted from this schema.
    - from_attributes=True enables loading directly from database/dictionary objects.
    - Any sensitive attributes in the internal data will never be serialized or returned.
    """
    model_config = ConfigDict(strict=False, from_attributes=True)

    username: str = Field(description="Unique username")
    email: EmailStr = Field(description="User email address")
    role: UserRole = Field(description="Role of the user (admin, critic, or viewer)")


class RegisterRequest(BaseModel):
    """Schema for new user registration."""
    model_config = ConfigDict(strict=False, str_strip_whitespace=True)

    username: str = Field(min_length=1, max_length=50, description="Unique username")
    email: EmailStr = Field(description="Registered email address")
    password: str = Field(min_length=1, description="Account password")
    role: UserRole = Field(default=UserRole.VIEWER, description="User role: 'admin', 'critic', or 'viewer'")


class LoginRequest(BaseModel):
    """Schema for user login credentials: only username and password."""
    model_config = ConfigDict(strict=False, str_strip_whitespace=True)

    username: str = Field(min_length=1, description="Account username")
    password: str = Field(min_length=1, description="Account password")


class MessageResponse(BaseModel):
    """Generic message response."""
    model_config = ConfigDict(strict=True)

    message: str = Field(description="Response status message")


class TokenResponse(BaseModel):
    """Schema for authentication token response."""
    access_token: str = Field(description="JWT access token")
    refresh_token: str = Field(description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")


class AccessTokenResponse(BaseModel):
    """Schema for access token only response (used by /refresh)."""
    access_token: str = Field(description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")


class RefreshTokenRequest(BaseModel):
    """Schema for token refresh request."""
    refresh_token: str = Field(description="Valid JWT refresh token")

