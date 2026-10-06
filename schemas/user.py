from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserResponse(BaseModel):
    """
    Public response schema for user profiles.
    - Password and password_hash are intentionally omitted from this schema.
    - from_attributes=True enables loading directly from database/dictionary objects.
    - Any sensitive attributes in the internal data will never be serialized or returned.
    """
    model_config = ConfigDict(strict=True, from_attributes=True)

    username: str = Field(description="Unique username")
    email: EmailStr = Field(description="User email address")
    role: str = Field(description="Role of the user (e.g. admin, member)")


class LoginRequest(BaseModel):
    """Schema for user login credentials."""
    model_config = ConfigDict(strict=True)

    email: EmailStr = Field(description="Registered email address")
    password: str = Field(min_length=1, description="Account password")


class RegisterRequest(LoginRequest):
    """Schema for new user registration."""
    model_config = ConfigDict(strict=True)

    name: str = Field(min_length=1, description="Full name of the user")


class MessageResponse(BaseModel):
    """Generic message response."""
    model_config = ConfigDict(strict=True)

    message: str = Field(description="Response status message")
