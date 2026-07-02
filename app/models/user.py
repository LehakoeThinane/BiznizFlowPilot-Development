"""User model - represents a person with access to the system."""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class User(BaseModel):
    """User entity - belongs to a business (multi-tenant)."""

    __tablename__ = "users"

    business_id = Column(
        Uuid,
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Tenant/business ID - CRITICAL FOR MULTI-TENANCY",
    )

    email = Column(
        String(255),
        nullable=False,
        index=True,
        doc="User email",
    )

    first_name = Column(
        String(100),
        nullable=False,
        doc="User first name",
    )

    last_name = Column(
        String(100),
        nullable=False,
        doc="User last name",
    )

    hashed_password = Column(
        String(255),
        nullable=False,
        doc="Bcrypt hashed password",
    )

    role = Column(
        String(50),
        default="staff",
        nullable=False,
        index=True,
        doc="User role: owner, manager, staff",
    )

    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        doc="Whether user account is active",
    )

    avatar_url = Column(
        String,
        nullable=True,
        doc="Profile picture as a data URL or external URL",
    )

    failed_login_attempts = Column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        doc="Consecutive failed login attempts since last success",
    )

    locked_until = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        doc="Account locked until this UTC time after too many failed logins",
    )

    # Relationships
    business = relationship(
        "Business",
        foreign_keys=[business_id],
        doc="Associated business/tenant",
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<User id={self.id} email='{self.email}' role='{self.role}'>"

    @property
    def full_name(self) -> str:
        """Get user's full name."""
        return f"{self.first_name} {self.last_name}"
