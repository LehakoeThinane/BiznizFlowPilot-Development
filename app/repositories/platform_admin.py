"""PlatformAdmin repository - data access for the cross-tenant platform_admins table.

Not a BaseRepository subclass - PlatformAdmin has no business_id, and must
never be queried alongside tenant `users`.
"""

from typing import Optional

from sqlalchemy.orm import Session

from app.models.platform_admin import PlatformAdmin


class PlatformAdminRepository:
    """Platform admin repository."""

    def __init__(self, db: Session):
        """Initialize with a DB session."""
        self.db = db

    def get_by_email(self, email: str) -> Optional[PlatformAdmin]:
        """Look up a platform admin by email."""
        return self.db.query(PlatformAdmin).filter(PlatformAdmin.email == email).first()

    def get_by_id(self, platform_admin_id) -> Optional[PlatformAdmin]:
        """Look up a platform admin by ID."""
        return self.db.query(PlatformAdmin).filter(PlatformAdmin.id == platform_admin_id).first()

    def list_all(self, skip: int = 0, limit: int = 50) -> list[PlatformAdmin]:
        """List platform admins."""
        return (
            self.db.query(PlatformAdmin)
            .order_by(PlatformAdmin.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count(self) -> int:
        """Count platform admins."""
        return self.db.query(PlatformAdmin).count()
