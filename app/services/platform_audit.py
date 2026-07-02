"""Platform audit logging - append-only trail of vendor-side actions.

A thin helper rather than a full service class: every platform-facing
endpoint/service calls record_audit() directly so failed/denied attempts
get logged at the exact point they're detected, not just successes.
"""

from typing import Any, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.platform_audit_log import PlatformAuditLog


def record_audit(
    db: Session,
    platform_admin_id: Optional[UUID],
    action: str,
    target_type: Optional[str] = None,
    target_id: Optional[UUID] = None,
    result: str = "success",
    meta_data: Optional[dict[str, Any]] = None,
) -> PlatformAuditLog:
    """Append an audit log entry. Caller is responsible for the surrounding commit."""
    entry = PlatformAuditLog(
        platform_admin_id=platform_admin_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        result=result,
        meta_data=meta_data or {},
    )
    db.add(entry)
    db.flush()
    return entry
