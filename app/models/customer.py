"""Customer model - contact/company information."""

from sqlalchemy import Column, ForeignKey, String, Text, Uuid

from app.models.base import BaseModel


class Customer(BaseModel):
    """Customer entity.
    
    Represents a contact or company that can have leads and tasks.
    Belongs to a business (multi-tenant).
    """

    __tablename__ = "customers"

    SAFE_CONTEXT_FIELDS = {
        "id",
        "name",
        "email",
        "phone",
        "company",
        "notes",
    }

    business_id = Column(
        Uuid,
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Tenant ID - CRITICAL FOR MULTI-TENANCY",
    )

    name = Column(
        String(255),
        nullable=False,
        index=True,
        doc="Customer name",
    )

    email = Column(
        String(255),
        nullable=True,
        index=True,
        doc="Customer email",
    )

    phone = Column(
        String(20),
        nullable=True,
        doc="Customer phone number",
    )

    company = Column(
        String(255),
        nullable=True,
        doc="Customer company name",
    )

    notes = Column(
        Text,
        nullable=True,
        doc="Additional notes about customer",
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<Customer id={self.id} name='{self.name}'>"
