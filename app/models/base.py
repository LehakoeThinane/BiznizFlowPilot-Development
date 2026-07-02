"""Base model with UUID and timestamps."""

import uuid
from typing import Any

from sqlalchemy import Column, DateTime, func
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Uuid


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""

    pass


class BaseModel(Base):
    """Base model with UUID and timestamp columns."""

    __abstract__ = True

    id = Column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        doc="Unique identifier",
    )

    created_at = Column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now(),
        nullable=False,
        doc="Creation timestamp",
    )

    updated_at = Column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        doc="Last update timestamp",
    )

    # Subclasses can override this to limit exposed template fields
    SAFE_CONTEXT_FIELDS: set[str] | None = None

    def to_context_dict(self) -> dict[str, Any]:
        """Convert model to context dictionary, filtering safe template fields.
        
        If SAFE_CONTEXT_FIELDS is defined, only those fields are exported.
        Otherwise it exports all columns except sensitive ones like passwords.
        """
        if self.SAFE_CONTEXT_FIELDS is not None:
            return {
                col: getattr(self, col)
                for col in self.SAFE_CONTEXT_FIELDS
                if hasattr(self, col)
            }
            
        excluded = {"hashed_password"}
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
            if column.name not in excluded
        }

    def __repr__(self) -> str:
        """String representation."""
        return f"<{self.__class__.__name__} id={self.id}>"


def enum_values(enum_cls: type) -> list[str]:
    """Return enum values for SQLAlchemy Enum columns.

    SQLAlchemy's native Enum type defaults to binding enum member names.
    The database schema in this project stores the lower-case enum values,
    so we explicitly tell SQLAlchemy to persist those values instead.
    """
    return [member.value for member in enum_cls]
