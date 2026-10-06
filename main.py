import sys
from pathlib import Path

# Ensure directory is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, Request
from fastapi.responses import Response

from core.config import settings
from core.logger import set_request_id, setup_logging
from exceptions.handlers import register_exception_handlers
from routes import films, reviews, users

from database.base import Base
from database.engine import engine
import models  # noqa: F401 - ensure models are registered with Base.metadata

# Initialize structured JSON logging
setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"Application started - API Version: {settings.API_VERSION}")
    yield
    print("Application shutting down")


app = FastAPI(
    title="Film Review Platform API",
    version=settings.API_VERSION,
    lifespan=lifespan,
)

# Register centralized domain exception handlers
register_exception_handlers(app)


@app.middleware("http")
async def request_id_logging_middleware(request: Request, call_next) -> Response:
    """
    Middleware that ensures every request has a request_id in context
    and injects X-Request-ID (and X-Trace-ID) headers in the response.
    """
    header_id = request.headers.get("X-Request-ID") or request.headers.get("X-Trace-ID")
    req_id = header_id.strip() if header_id and header_id.strip() else str(uuid.uuid4())
    set_request_id(req_id)

    response = await call_next(request)
    response.headers["X-Request-ID"] = req_id
    response.headers["X-Trace-ID"] = req_id
    return response


# Register routers under /api/v1 (or configurable API version)
api_prefix = f"/api/{settings.API_VERSION}"
app.include_router(films.router, prefix=api_prefix)
app.include_router(reviews.router, prefix=api_prefix)
app.include_router(users.router, prefix=api_prefix)


@app.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "ok",
        "api_version": settings.API_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
