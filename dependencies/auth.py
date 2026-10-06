import uuid
from typing import Any
from fastapi import Depends

from core.config import Settings
from dependencies.config import get_config


def get_current_user(config: Settings = Depends(get_config)) -> dict[str, Any]:
    """
    Reusable dependency demonstrating dependency chaining.
    Depends on get_config to access configuration (e.g. token secret key).
    Returns a simple placeholder user object.
    """
    # Note: Using config internally without exposing secrets to callers
    _ = config.TOKEN_SECRET_KEY
    return {
        "user_id": uuid.UUID("00000000-0000-0000-0000-000000000042"),
        "username": "reviewer_alex",
        "role": "authenticated_user",
    }
