from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    SQLAlchemy 2.0 DeclarativeBase for all ORM models.
    All models must inherit from this Base.
    """
    pass
