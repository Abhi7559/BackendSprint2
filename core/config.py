import os
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from core.secrets import get_secrets


class Settings(BaseSettings):
    """
    Centralized typed configuration.
    Non-sensitive values are loaded from environment / .env.
    Sensitive credentials (DATABASE_PASSWORD, TOKEN_SECRET_KEY) are sourced
    dynamically from AWS Secrets Manager (Floci) via core.secrets.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Non-sensitive database connection parameters
    DB_USER: str = Field(default="user", description="Database user name")
    DB_HOST: str = Field(default="localhost", description="Database host")
    DB_PORT: int = Field(default=5432, description="Database port")
    DB_NAME: str = Field(default="film_review", description="Database name")

    # Optional fallback or override for DATABASE_URL if explicitly set (e.g. SQLite in unit tests)
    DATABASE_URL_OVERRIDE: Optional[str] = Field(default=None, alias="DATABASE_URL")

    # Non-sensitive token expiration settings
    TOKEN_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, description="Access token expiry duration in minutes")
    TOKEN_REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, description="Refresh token expiry duration in days")

    # CORS & Versioning
    CORS_ORIGINS: list[str] = Field(default=["http://localhost:3000"], description="Allowed CORS origins")
    API_VERSION: str = Field(default="v1", description="API version string")

    # Cache
    REDIS_URL: str = Field(default="redis://localhost:6379/0", description="Redis connection URL")
    FILM_LIST_CACHE_TTL_SECONDS: int = Field(default=300, description="Cache TTL for film listings in seconds")

    # Floci / AWS Secrets Manager settings
    AWS_SECRET_ID: str = Field(default="film-review/platform", description="Secrets Manager secret identifier")
    AWS_SECRETS_ENDPOINT_URL: str = Field(default="http://localhost:4566", description="Floci / Local AWS endpoint")
    AWS_DEFAULT_REGION: str = Field(default="us-east-1", description="AWS region")

    @property
    def DATABASE_URL(self) -> str:
        """
        Dynamically assembles the asyncpg database connection URL using the
        password retrieved from AWS Secrets Manager.
        """
        if self.DATABASE_URL_OVERRIDE:
            # If an explicit DATABASE_URL was provided (e.g. in test fixtures sqlite+aiosqlite)
            return self.DATABASE_URL_OVERRIDE

        secrets = get_secrets()
        return (
            f"postgresql+asyncpg://{self.DB_USER}:{secrets.DATABASE_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def TOKEN_SECRET_KEY(self) -> str:
        """
        Dynamically retrieves the JWT signing key from AWS Secrets Manager.
        """
        secrets = get_secrets()
        return secrets.JWT_SECRET_KEY

    @property
    def THIRD_PARTY_API_KEY(self) -> Optional[str]:
        """
        Dynamically retrieves optional third-party API key from AWS Secrets Manager.
        """
        secrets = get_secrets()
        return secrets.THIRD_PARTY_API_KEY


# Single shared configuration object instantiated once
settings = Settings()
