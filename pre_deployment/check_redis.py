"""
pre_deployment/check_redis.py

Standalone Redis connectivity verification using redis-py.
Does NOT import routes, handlers, services, models, or any application logic.
"""
import os
import sys
from pathlib import Path
import redis

# Attempt to load from .env if running standalone outside Docker
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
except ImportError:
    pass


def check_redis() -> None:
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        print("[ERROR] REDIS_URL environment variable is missing or empty.", file=sys.stderr)
        sys.exit(1)

    # Hide password in logs if present
    masked_url = redis_url
    if "@" in redis_url:
        prefix, target = redis_url.split("@", 1)
        scheme = prefix.split("://")[0]
        masked_url = f"{scheme}://***:***@{target}"

    print(f"--> [Pre-Deployment] Checking Redis connection to: {masked_url}")

    try:
        client = redis.from_url(redis_url, socket_connect_timeout=5, socket_timeout=5)
        if not client.ping():
            raise redis.ConnectionError("Redis PING responded False")
        print("[SUCCESS] Redis instance is reachable and healthy.")
    except (redis.ConnectionError, redis.TimeoutError) as err:
        print(f"[FATAL] Cannot connect to Redis at target: {masked_url}", file=sys.stderr)
        print(f"Redis error details: {err}", file=sys.stderr)
        sys.exit(1)
    except Exception as err:
        print(f"[FATAL] Unexpected error connecting to Redis: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    check_redis()
