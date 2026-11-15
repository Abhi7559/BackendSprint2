"""
pre_deployment/check_db.py

Standalone database connectivity verification using SQLAlchemy.
Does NOT import routes, handlers, services, models, or any application logic.
"""
import asyncio
import os
import sys
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine

# Attempt to load from .env if running standalone outside Docker
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
except ImportError:
    pass


async def async_check_database() -> None:
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("[ERROR] DATABASE_URL environment variable is missing or empty.", file=sys.stderr)
        sys.exit(1)

    # Hide password in logs if present
    masked_url = db_url
    if "@" in db_url:
        prefix, target = db_url.split("@", 1)
        scheme = prefix.split("://")[0]
        masked_url = f"{scheme}://***:***@{target}"

    print(f"--> [Pre-Deployment] Checking Database connection to: {masked_url}")

    try:
        # Create async engine with a connection timeout
        engine = create_async_engine(
            db_url,
            pool_pre_ping=True,
            connect_args={"timeout": 5} if "asyncpg" in db_url else {},
        )
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        await engine.dispose()
        print("[SUCCESS] Database is reachable and healthy.")
    except SQLAlchemyError as err:
        print(f"[FATAL] Cannot connect to database at target: {masked_url}", file=sys.stderr)
        print(f"Database error details: {err}", file=sys.stderr)
        sys.exit(1)
    except Exception as err:
        print(f"[FATAL] Unexpected error connecting to database: {err}", file=sys.stderr)
        sys.exit(1)


def check_database() -> None:
    asyncio.run(async_check_database())


if __name__ == "__main__":
    check_database()

