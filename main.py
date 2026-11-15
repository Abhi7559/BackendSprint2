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
from routes import films, reviews, ui, users

from database.base import Base
from database.engine import engine
import models  # noqa: F401 - ensure models are registered with Base.metadata

from database.redis import close_redis, init_redis

# Initialize structured JSON logging
setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"Application started - API Version: {settings.API_VERSION}")
    try:
        await init_redis()
    except Exception as e:
        print(f"Redis initialization warning (will retry on demand): {e}")
    yield
    print("Application shutting down")
    await close_redis()


app = FastAPI(
    title="Film Review Platform API",
    version=settings.API_VERSION,
    lifespan=lifespan,
)

from time import perf_counter
from fastapi.middleware.cors import CORSMiddleware

# Register centralized domain exception handlers
register_exception_handlers(app)

# 1. CORS Configuration: Permit ONLY http://localhost:3000 (No wildcards)
# Only methods and headers needed by the frontend are explicitly allowed
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Request-ID", "X-Trace-ID"],
    expose_headers=["X-Request-ID", "X-Trace-ID", "X-Process-Time-Ms"],
)




# 2. Response-Time Middleware: Measures total duration in milliseconds
@app.middleware("http")
async def response_time_middleware(request: Request, call_next) -> Response:
    """
    Measures the total processing time of each request and appends it
    to the response as 'X-Process-Time-Ms' in milliseconds.
    """
    start_time = perf_counter()
    response = await call_next(request)
    duration_ms = (perf_counter() - start_time) * 1000
    response.headers["X-Process-Time-Ms"] = f"{duration_ms:.2f}"
    return response


# 3. Request-ID & Logging Middleware
@app.middleware("http")
async def request_id_logging_middleware(request: Request, call_next) -> Response:
    """
    Middleware that generates/extracts a unique identifier per request,
    attaches it to logger context (so every log entry carries it end-to-end),
    and injects X-Request-ID and X-Trace-ID headers in the response.
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

# Server-rendered HTML UI router (completely separate from JSON API routes)
app.include_router(ui.router)


@app.get("/", include_in_schema=False)
def root():
    return {
        "status": "online",
        "service": "Film Review Platform API",
        "version": settings.API_VERSION,
        "docs_url": "/docs",
    }


@app.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "ok",
        "api_version": settings.API_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
