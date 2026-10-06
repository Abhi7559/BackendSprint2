import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from core.logger import get_request_id
from exceptions.domain import (
    FilmNotFoundError,
    ReviewNotFoundError,
    DuplicateReviewError,
    UnauthorisedReviewAccessError,
    FilmHasActiveReviewsError,
    EmailAlreadyExistsError,
    InvalidCredentialsError,
)

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    """Register centralized exception handlers for domain exceptions on FastAPI."""

    @app.exception_handler(EmailAlreadyExistsError)
    async def email_already_exists_handler(request: Request, exc: EmailAlreadyExistsError) -> JSONResponse:
        logger.warning(
            f"EmailAlreadyExistsError handled: {exc}",
            extra={"request_id": get_request_id()},
        )
        return JSONResponse(
            status_code=400,
            content={
                "type": "EmailAlreadyExistsError",
                "message": str(exc),
                "detail": {
                    "email": exc.email,
                },
            },
        )

    @app.exception_handler(InvalidCredentialsError)
    async def invalid_credentials_handler(request: Request, exc: InvalidCredentialsError) -> JSONResponse:
        logger.warning(
            f"InvalidCredentialsError handled: {exc}",
            extra={"request_id": get_request_id()},
        )
        return JSONResponse(
            status_code=401,
            content={
                "type": "InvalidCredentialsError",
                "message": str(exc),
                "detail": {},
            },
        )

    @app.exception_handler(FilmNotFoundError)
    async def film_not_found_handler(request: Request, exc: FilmNotFoundError) -> JSONResponse:
        logger.warning(
            f"FilmNotFoundError handled: {exc}",
            extra={"request_id": get_request_id()},
        )
        return JSONResponse(
            status_code=404,
            content={
                "type": "FilmNotFoundError",
                "message": str(exc),
                "detail": {
                    "film_id": str(exc.film_id),
                },
            },
        )

    @app.exception_handler(ReviewNotFoundError)
    async def review_not_found_handler(request: Request, exc: ReviewNotFoundError) -> JSONResponse:
        logger.warning(
            f"ReviewNotFoundError handled: {exc}",
            extra={"request_id": get_request_id()},
        )
        return JSONResponse(
            status_code=404,
            content={
                "type": "ReviewNotFoundError",
                "message": str(exc),
                "detail": {
                    "review_id": str(exc.review_id),
                },
            },
        )

    @app.exception_handler(DuplicateReviewError)
    async def duplicate_review_handler(request: Request, exc: DuplicateReviewError) -> JSONResponse:
        logger.warning(
            f"DuplicateReviewError handled: {exc}",
            extra={"request_id": get_request_id()},
        )
        return JSONResponse(
            status_code=409,
            content={
                "type": "DuplicateReviewError",
                "message": str(exc),
                "detail": {
                    "user_id": str(exc.user_id),
                    "film_id": str(exc.film_id),
                },
            },
        )

    @app.exception_handler(UnauthorisedReviewAccessError)
    async def unauthorised_review_access_handler(request: Request, exc: UnauthorisedReviewAccessError) -> JSONResponse:
        logger.warning(
            f"UnauthorisedReviewAccessError handled: {exc}",
            extra={"request_id": get_request_id()},
        )
        return JSONResponse(
            status_code=403,
            content={
                "type": "UnauthorisedReviewAccessError",
                "message": str(exc),
                "detail": {
                    "review_id": str(exc.review_id),
                    "user_id": str(exc.user_id),
                },
            },
        )

    @app.exception_handler(FilmHasActiveReviewsError)
    async def film_has_active_reviews_handler(request: Request, exc: FilmHasActiveReviewsError) -> JSONResponse:
        logger.warning(
            f"FilmHasActiveReviewsError handled: {exc}",
            extra={"request_id": get_request_id()},
        )
        return JSONResponse(
            status_code=409,
            content={
                "type": "FilmHasActiveReviewsError",
                "message": str(exc),
                "detail": {
                    "film_id": str(exc.film_id),
                },
            },
        )
