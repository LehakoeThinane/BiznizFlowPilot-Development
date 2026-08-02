"""Customer portal service - durable, revocable external document access.

See app/models/customer_portal_access.py for the design rationale (hashed
token like the meeting-RSVP pattern, explicit revocation like
DocumentShareLink, business_id-scoped throughout since customer_id already
carries an unambiguous path to it - no unscoped-lookup exception needed
here, unlike DocumentShareLink's public redemption).
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.permissions import PRIVILEGED_ROLES, require_role
from app.integrations import object_storage
from app.models.customer import Customer
from app.models.customer_portal_access import CustomerPortalAccess
from app.models.document import Document
from app.repositories.business import BusinessRepository
from app.repositories.customer import CustomerRepository
from app.repositories.customer_portal_access import CustomerPortalAccessRepository
from app.repositories.document import DocumentRepository
from app.schemas.auth import CurrentUser


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


class CustomerPortalService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = CustomerPortalAccessRepository(db)
        self.customer_repo = CustomerRepository(db)
        self.document_repo = DocumentRepository(db)
        self.business_repo = BusinessRepository(db)

    # --- authenticated side ---

    def generate_or_regenerate(
        self, business_id: UUID, current_user: CurrentUser, customer_id: UUID,
    ) -> tuple[CustomerPortalAccess, str] | None:
        require_role(current_user, PRIVILEGED_ROLES, "manage the customer portal")
        customer = self.customer_repo.get(business_id=business_id, entity_id=customer_id)
        if not customer:
            return None

        existing = self.repo.get_active_for_customer(customer_id)
        if existing:
            existing.revoked_at = datetime.now(timezone.utc)
            self.db.commit()

        raw_token = secrets.token_urlsafe(32)
        access = self.repo.create(customer_id=customer_id, created_by=current_user.user_id, token_hash=_hash_token(raw_token))
        return access, raw_token

    def revoke(self, business_id: UUID, current_user: CurrentUser, customer_id: UUID) -> bool:
        require_role(current_user, PRIVILEGED_ROLES, "manage the customer portal")
        customer = self.customer_repo.get(business_id=business_id, entity_id=customer_id)
        if not customer:
            return False

        access = self.repo.get_active_for_customer(customer_id)
        if not access:
            return False

        access.revoked_at = datetime.now(timezone.utc)
        self.db.commit()
        return True

    def get_status(
        self, business_id: UUID, current_user: CurrentUser, customer_id: UUID,
    ) -> CustomerPortalAccess | None:
        """Authenticated-side 'is a link active / when was it last used'
        display. Never returns a token."""
        customer = self.customer_repo.get(business_id=business_id, entity_id=customer_id)
        if not customer:
            return None
        return self.repo.get_active_for_customer(customer_id)

    # --- public, unauthenticated side ---

    def resolve(self, raw_token: str) -> Customer | None:
        access = self.repo.get_by_token_hash(_hash_token(raw_token))
        if not access or access.revoked_at is not None:
            return None
        access.last_accessed_at = datetime.now(timezone.utc)
        self.db.commit()
        return self.customer_repo.get(business_id=access.customer.business_id, entity_id=access.customer_id)

    def list_documents(self, raw_token: str) -> tuple[Customer, str, list[Document]] | None:
        customer = self.resolve(raw_token)
        if not customer:
            return None
        business = self.business_repo.get_by_id(customer.business_id)
        business_name = business.name if business else ""
        docs = [
            doc for doc in self.document_repo.get_by_entity(customer.business_id, "customer", customer.id)
            if not doc.restricted
        ]
        return customer, business_name, docs

    def get_document_download_url(self, raw_token: str, document_id: UUID) -> str | None:
        """Defense in depth: re-validates the requested document actually
        belongs to this token's own customer before minting a URL - a
        client can't reuse their token to fetch another customer's document."""
        customer = self.resolve(raw_token)
        if not customer:
            return None

        doc = self.document_repo.get(business_id=customer.business_id, entity_id=document_id)
        if not doc or doc.entity_type != "customer" or str(doc.entity_id) != str(customer.id):
            return None
        if doc.restricted:
            return None

        return object_storage.presigned_download_url(doc.storage_key, doc.filename, disposition="attachment")
