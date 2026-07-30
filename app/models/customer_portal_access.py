"""CustomerPortalAccess model - a durable, revocable, hashed-at-rest token
granting one Customer's external contact standing (not time-limited)
access to that customer's documents via the public client portal.

Combines DocumentShareLink's explicit revocation (revoked_at column) with
MeetingExternalParticipant's hash-at-rest storage (token_hash, not the raw
token - the raw value only ever exists in the one-time reveal to the
creating user, exactly like a generated API key). Unlike DocumentShareLink,
this keeps business_id-reachability intact throughout: the token resolves
to a customer_id, and Customer.business_id is available from there, so
every downstream query (documents, business name for the portal page)
stays business_id-scoped - no unscoped-lookup exception needed here.

One active row per customer: regenerating replaces (revokes) the previous
token rather than allowing multiple concurrent live links, matching the
product ask of a single durable client-facing link.
"""

from sqlalchemy import Column, DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class CustomerPortalAccess(BaseModel):
    __tablename__ = "customer_portal_access"

    customer_id = Column(Uuid, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by = Column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    token_hash = Column(
        String(128),
        nullable=False,
        unique=True,
        doc="SHA-256 hash of the raw token - the raw value is never persisted, "
            "only revealed once to the staff member who generates it.",
    )
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    last_accessed_at = Column(DateTime(timezone=True), nullable=True, doc="Staff-visible security signal.")

    customer = relationship("Customer")
    creator = relationship("User", foreign_keys=[created_by])

    def __repr__(self) -> str:
        return f"<CustomerPortalAccess id={self.id} customer_id={self.customer_id} revoked={self.revoked_at is not None}>"
