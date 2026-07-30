"""CustomerPortalAccess repository.

Not a BaseRepository subclass - like DocumentShareLink, this model has no
business_id (BaseRepository.create() unconditionally injects business_id,
which isn't a valid column here). Tenant safety is enforced in the service
layer via the parent Customer's business_id before an access row is ever
created (see CustomerPortalService.generate_or_regenerate).
"""

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.customer_portal_access import CustomerPortalAccess


class CustomerPortalAccessRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_active_for_customer(self, customer_id: UUID) -> CustomerPortalAccess | None:
        return (
            self.db.query(CustomerPortalAccess)
            .filter(
                CustomerPortalAccess.customer_id == customer_id,
                CustomerPortalAccess.revoked_at.is_(None),
            )
            .first()
        )

    def get_by_token_hash(self, token_hash: str) -> CustomerPortalAccess | None:
        return self.db.query(CustomerPortalAccess).filter(CustomerPortalAccess.token_hash == token_hash).first()

    def create(self, customer_id: UUID, created_by: UUID, token_hash: str) -> CustomerPortalAccess:
        access = CustomerPortalAccess(customer_id=customer_id, created_by=created_by, token_hash=token_hash)
        self.db.add(access)
        self.db.commit()
        self.db.refresh(access)
        return access
