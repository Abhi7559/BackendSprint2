from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class ReviewBase(BaseModel):
    """Base schema holding common review attributes."""
    model_config = ConfigDict(strict=True)

    rating: int = Field(ge=1, le=10, description="Rating score from 1 to 10 inclusive")
    body: str = Field(min_length=50, description="Review feedback containing at least 50 characters")


class ReviewCreate(ReviewBase):
    """
    Schema for creating a review.
    Contains rating and body; film_id is provided via the URL path.
    """
    pass


class ReviewResponse(ReviewBase):
    """
    Schema returned to the client when a review is submitted.
    Includes film_id from URL path along with response metadata.
    """
    id: UUID = Field(description="Unique review identifier")
    film_id: UUID = Field(description="Unique identifier of the film being reviewed")
    reviewer_name: str = Field(description="Display name of the reviewer")
    submitted_at: datetime = Field(description="Timestamp when the review was created")


class ReviewUpdate(BaseModel):
    """Schema for updating an existing review."""
    model_config = ConfigDict(strict=True)

    rating: int | None = Field(default=None, ge=1, le=10)
    body: str | None = Field(default=None, min_length=50)


class ReviewDeleteResponse(BaseModel):
    """Response returned when a review is deleted."""
    model_config = ConfigDict(strict=True)

    status: str = Field(default="success", description="Status of the operation")
    message: str = Field(description="Informational message about the deletion")
    review_id: UUID = Field(description="ID of the deleted review")
    trace_id: str = Field(description="Auto-generated unique request trace ID")
