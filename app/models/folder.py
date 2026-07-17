"""Folder model - a nested container for documents not tied to a CRM record.

Documents attach to a folder the exact same way they attach to a lead or
task: entity_type="folder", entity_id=<folder.id>. This reuses sharing,
restricted-access requests, and checkout/versioning unmodified - a folder
is just another kind of entity, not a special case.
"""

from sqlalchemy import Column, ForeignKey, Index, String, Uuid
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class Folder(BaseModel):
    __tablename__ = "folders"
    __table_args__ = (
        Index("ix_folders_business_parent", "business_id", "parent_folder_id"),
    )

    business_id = Column(
        Uuid, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True,
        doc="Tenant ID - CRITICAL FOR MULTI-TENANCY",
    )
    parent_folder_id = Column(
        Uuid, ForeignKey("folders.id", ondelete="CASCADE"), nullable=True,
        doc="Null for a top-level folder",
    )
    name = Column(String(255), nullable=False)
    created_by = Column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    creator = relationship("User", foreign_keys=[created_by])

    def __repr__(self) -> str:
        return f"<Folder id={self.id} name='{self.name}'>"
