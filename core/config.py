from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Centralized typed configuration loaded from .env.
    Fails fast if any required setting is missing or invalid.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str = Field(description="Database connection URL")
    TOKEN_SECRET_KEY: str = Field(description="Secret key used for token signing")
    TOKEN_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(description="Access token expiry duration in minutes")
    TOKEN_REFRESH_TOKEN_EXPIRE_DAYS: int = Field(description="Refresh token expiry duration in days")
    CORS_ORIGINS: list[str] = Field(default=["http://localhost:3000"], description="Allowed CORS origins")
    API_VERSION: str = Field(description="API version string")
    REDIS_URL: str = Field(default="redis://localhost:6379/0", description="Redis connection URL")
    FILM_LIST_CACHE_TTL_SECONDS: int = Field(default=300, description="Cache TTL for film listings in seconds")


# Single shared configuration object instantiated once at import time
settings = Settings()
