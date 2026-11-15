"""
pre_deployment/check_db.py

Standalone database connectivity verification using SQLAlchemy.
Does NOT import routes, handlers, services, models, or any application logic.
Slices dynamic DATABASE_URL using the password from AWS Secrets Manager
(via settings.DATABASE_URL) while supporting explicit DATABASE_URL overrides.
"""
import asyncio
import os
import sys
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine

# Add project root to sys.path so core can be imported
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from core.config import settings


async def async_check_database() -> None:
    try:
        db_url = settings.DATABASE_URL
    except Exception as e:
        print(f"[FATAL] Cannot assemble DATABASE_URL (Secrets Manager error): {e}", file=sys.stderr)
        sys.exit(1)

    if not db_url:
        print("[ERROR] DATABASE_URL is missing or empty.", file=sys.stderr)
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
