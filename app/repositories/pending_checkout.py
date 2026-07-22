"""PendingCheckout repository.

Not a BaseRepository subclass - like DocumentAccessRequest, this model has
no business_id (it exists before any Organization/Business does; that's the
whole point of it).
"""

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.pending_checkout import PendingCheckout


class PendingCheckoutRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self, org_name: str, subsidiary_name: str, owner_email: str, business_email: str, plan_tier: str
    ) -> PendingCheckout:
        pending = PendingCheckout(
            org_name=org_name,
            subsidiary_name=subsidiary_name,
            owner_email=owner_email,
            business_email=business_email,
            plan_tier=plan_tier,
        )
        self.db.add(pending)
        self.db.commit()
        self.db.refresh(pending)
        return pending

    def get(self, pending_id: UUID) -> PendingCheckout | None:
        return self.db.query(PendingCheckout).filter(PendingCheckout.id == pending_id).first()
