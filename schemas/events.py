from datetime import datetime, timezone
from typing import Any, Union
from uuid import UUID
from pydantic import BaseModel, Field


class ReviewEvent(BaseModel):
    """
    Lightweight, reusable domain event schema for review lifecycle events.
    Contains only event_type, resource_id, and timezone-aware UTC timestamp.
    Does NOT contain sensitive user data, passwords, or full review body.
    """
    event_type: str = Field(
        ...,
        description="Event classification, e.g. review.created, review.updated",
        examples=["review.created", "review.updated"],
    )
    resource_id: Union[str, int] = Field(
        ...,
        description="The primary key ID of the target resource (review ID)",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timezone-aware UTC timestamp of when the event was generated",
    )

    model_config = {
        "json_encoders": {
            datetime: lambda dt: dt.isoformat(),
            UUID: lambda u: str(u),
        }
    }
