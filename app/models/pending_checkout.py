"""PendingCheckout model - carries self-serve signup intent across a PayFast
checkout redirect.

PayFast has no server-side "session" object the way Stripe's Checkout Session
does - checkout is a signed redirect to their hosted payment page, and all we
get back is whatever we passed them (echoed in the ITN). This row is what we
pass: its id becomes m_payment_id, and the ITN handler looks it back up to
know which org/email/plan to provision.

Deliberately a plain String status with a CHECK constraint, not a native
Postgres enum - same convention as DocumentAccessRequest.status, avoids the
enum-migration-drift class of bug.
"""

from sqlalchemy import CheckConstraint, Column, String

from app.models.base import BaseModel


class PendingCheckout(BaseModel):
    __tablename__ = "pending_checkouts"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'completed')", name="ck_pending_checkouts_status"),
    )

    org_name = Column(String(255), nullable=False)
    subsidiary_name = Column(String(255), nullable=True)
    owner_email = Column(String(255), nullable=False)
    plan_tier = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False, default="pending", server_default="pending")

    def __repr__(self) -> str:
        return f"<PendingCheckout id={self.id} org_name='{self.org_name}' status='{self.status}'>"
