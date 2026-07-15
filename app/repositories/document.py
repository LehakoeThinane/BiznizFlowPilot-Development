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
