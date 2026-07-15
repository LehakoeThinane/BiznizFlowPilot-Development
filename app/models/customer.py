"""Customer model - contact/company information."""

from sqlalchemy import Column, ForeignKey, Index, String, Text, Uuid, text

from app.models.base import BaseModel


class Customer(BaseModel):
    """Customer entity.

    Represents a contact or company that can have leads and tasks.
    Belongs to a business (multi-tenant).
    """

    __tablename__ = "customers"
    __table_args__ = (
        Index(
            "uq_customers_business_external_ref",
            "business_id",
            "external_ref",
            unique=True,
            postgresql_where=text("external_ref IS NOT NULL"),
        ),
    )

    SAFE_CONTEXT_FIELDS = {
        "id",
        "name",
        "email",
        "phone",
        "company",
        "website",
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

    website = Column(
        String(500),
        nullable=True,
        doc="Customer/company website",
    )

    external_ref = Column(
        String(255),
        nullable=True,
        doc="Provider-tagged dedup key for lead-gen imports, e.g. "
            "'google_places:<place_id>' - NULL for manually-created customers.",
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<Customer id={self.id} name='{self.name}'>"
