"""Document repository - data access layer."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.document import Document
from app.repositories.base import BaseRepository


class DocumentRepository(BaseRepository[Document]):
    """Document repository with business_id filtering.

    🧨 CRITICAL: Every method automatically filters by business_id.
    """

    def __init__(self, db: Session):
        super().__init__(db, Document)

    def get_by_entity(self, business_id: UUID, entity_type: str, entity_id: UUID) -> list[Document]:
        """Get documents attached to an entity within business.

        🧨 CRITICAL: Filters by business_id.
        """
        return (
            self.db.query(Document)
            .filter(
                Document.business_id == business_id,
                Document.entity_type == entity_type,
                Document.entity_id == entity_id,
            )
            .order_by(Document.created_at.desc())
            .all()
        )

    def get_by_id_for_public_share(self, document_id: UUID) -> Document | None:
        """🧨 The one sanctioned unscoped lookup on this model - used only by the
        public, unauthenticated share-link redemption flow (DocumentShareService.
        resolve_public_download), where a cryptographically random, unguessable
        token has already been validated as the caller's sole credential in
        place of a business_id. Never call this from any authenticated path."""
        return self.db.query(Document).filter(Document.id == document_id).first()
