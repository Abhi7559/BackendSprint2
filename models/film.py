import uuid
from typing import TYPE_CHECKING
from sqlalchemy import String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base

if TYPE_CHECKING:
    from models.review import Review


class Film(Base):
    __tablename__ = "films"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    release_year: Mapped[int] = mapped_column(nullable=False)
    genre: Mapped[str] = mapped_column(String(100), nullable=False)
    director: Mapped[str] = mapped_column(String(200), nullable=False)
    is_deleted: Mapped[bool] = mapped_column(default=False, nullable=False)

    # 1-to-many relationship: One film has many reviews
    reviews: Mapped[list["Review"]] = relationship(
        back_populates="film",
        cascade="all, delete-orphan",
    )
