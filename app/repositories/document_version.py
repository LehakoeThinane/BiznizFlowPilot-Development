"""DocumentVersion repository.

Not a BaseRepository subclass - like the other document-adjacent models,
tenant safety is enforced in the service layer via the parent Document's
business_id, not a column on this table.
"""

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.document_version import DocumentVersion


class DocumentVersionRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self, document_id: UUID, version_number: int, uploaded_by: UUID | None,
        filename: str, content_type: str | None, size_bytes: int, storage_key: str,
    ) -> DocumentVersion:
        version = DocumentVersion(
            document_id=document_id,
            version_number=version_number,
            uploaded_by=uploaded_by,
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
            storage_key=storage_key,
        )
        self.db.add(version)
        self.db.flush()
        return version

    def get(self, version_id: UUID) -> DocumentVersion | None:
        return self.db.query(DocumentVersion).filter(DocumentVersion.id == version_id).first()

    def list_for_document(self, document_id: UUID) -> list[DocumentVersion]:
        return (
            self.db.query(DocumentVersion)
            .filter(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.version_number.desc())
            .all()
        )
