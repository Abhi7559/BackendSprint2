from __future__ import annotations

from datetime import datetime
from typing import Self
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator


class FilmBase(BaseModel):
    """Base schema holding common film attributes."""
    model_config = ConfigDict(strict=False, str_strip_whitespace=True, from_attributes=True)

    title: str = Field(min_length=1, description="Title of the film (cannot be empty)")
    release_year: int = Field(description="Year the film was released (must be an integer)")
    genre: str = Field(min_length=1, description="Genre of the film (e.g. Sci-Fi, Action)")
    director: str = Field(min_length=1, description="Full name of the film director")


class FilmCreate(FilmBase):
    """
    Schema for creating a new film.
    Inherits all common fields from FilmBase.
    """
    pass


class FilmResponse(FilmBase):
    """
    Schema returned to the client when a film is created or retrieved.
    Inherits title, release_year, genre, and director from FilmBase,
    and adds the database id and a computed 'years_ago' field.
    """
    id: UUID = Field(description="Unique identifier of the film")

    @computed_field
    @property
    def years_ago(self) -> int:
        """
        Computes how many years ago the film was released
        relative to the current year.
        """
        current_calendar_year = datetime.now().year
        return current_calendar_year - self.release_year


class ReleaseWindow(BaseModel):
    """
    Schema demonstrating cross-field validation with @model_validator.
    Ensures start_year <= end_year.
    """
    model_config = ConfigDict(strict=True)

    start_year: int = Field(description="Starting year of the release window")
    end_year: int = Field(description="Ending year of the release window")

    @model_validator(mode="after")
    def validate_release_year_range(self) -> Self:
        """
        Validates that the starting year is not greater than the ending year.
        """
        if self.start_year > self.end_year:
            raise ValueError("start_year must be less than or equal to end_year")
        return self


class FilmUpdate(BaseModel):
    """Schema for updating an existing film."""
    model_config = ConfigDict(strict=True, str_strip_whitespace=True)

    title: str | None = None
    release_year: int | None = None
    genre: str | None = None
    director: str | None = None


class FilmListResponse(BaseModel):
    """Envelope response containing films list, trace identifier, and metadata."""
    model_config = ConfigDict(from_attributes=True)

    status: str = Field(default="success", description="Status of the response")
    trace_id: str = Field(description="Auto-generated unique request trace ID")
    total: int = Field(description="Total number of films returned")
    data: list[FilmResponse] = Field(description="List of film items")


class FilmDeleteResponse(BaseModel):
    """Response returned when a film is deleted."""
    model_config = ConfigDict(strict=True)

    status: str = Field(default="success", description="Status of the operation")
    message: str = Field(description="Informational message about the deletion")
    film_id: UUID = Field(description="ID of the deleted film")
    trace_id: str = Field(description="Auto-generated unique request trace ID")
