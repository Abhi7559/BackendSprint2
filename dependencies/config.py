from core.config import Settings, settings


def get_config() -> Settings:
    """
    Reusable dependency function that provides the shared application configuration.
    Returns the single configuration object instantiated at import time.
    """
    return settings
