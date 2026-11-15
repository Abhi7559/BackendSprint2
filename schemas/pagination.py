from typing import Generic, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationParams(BaseModel):
    """
    Query parameters for offset-based pagination.
    page: 1-indexed page number (defaults to 1).
    page_size: number of items per page (defaults to 10, max 100).
    """
    page: int = Field(default=1, ge=1, description="Current page number (1-indexed)")
    page_size: int = Field(default=10, ge=1, le=100, description="Number of items per page")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Envelope response for offset-based paginated endpoints.
    Includes page number, page size, total record count, total pages, and the items.
    """
    items: list[T] = Field(description="Records for the current page")
    page: int = Field(description="Current page number")
    page_size: int = Field(description="Items per page")
    total: int = Field(description="Total count of matching records across all pages")
    total_pages: int = Field(description="Total number of pages available")


class FilmFilterParams(BaseModel):
    """
    Query filters for films catalogue.
    All filters are optional and can be combined freely.
    """
    genre: str | None = Field(default=None, description="Exact match on film genre")
    from_year: int | None = Field(default=None, description="Lower bound for release year (inclusive)")
    to_year: int | None = Field(default=None, description="Upper bound for release year (inclusive)")
    director: str | None = Field(default=None, description="Case-insensitive substring match on director name")


class ReviewFilterParams(BaseModel):
    """
    Query filters for reviews list.
    """
    min_rating: int | None = Field(default=None, ge=1, le=5, description="Minimum rating (1-5)")
    max_rating: int | None = Field(default=None, ge=1, le=5, description="Maximum rating (1-5)")


class CursorPageResponse(BaseModel, Generic[T]):
    """
    Envelope response for cursor-based pagination.
    next_cursor is null when no further records exist.
    """
    items: list[T] = Field(description="List of records for the current batch")
    next_cursor: str | None = Field(default=None, description="Opaque cursor token for next page (null if last page)")
