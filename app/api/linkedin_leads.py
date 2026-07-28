"""Platform-admin routes for LinkedIn ad lead management.

🧨 Gated on get_current_platform_admin (any active platform admin), not
require_platform_role - importing/triaging a sales-lead CSV isn't in the
same sensitivity tier as the routes that already restrict to admin/
super_admin (e.g. issuing platform-admin credentials). See
app/dependencies_platform.py.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies_platform import get_current_platform_admin
from app.repositories.linkedin_lead import LinkedInLeadRepository
from app.schemas.linkedin_lead import LinkedInLeadImportResult, LinkedInLeadOut, LinkedInLeadUpdate
from app.schemas.platform import CurrentPlatformAdmin
from app.services.linkedin_leads import LinkedInLeadImportService

router = APIRouter(prefix="/platform/v1/linkedin-leads", tags=["platform-admin"])


@router.post("/import", response_model=LinkedInLeadImportResult, status_code=201)
async def import_linkedin_leads_csv(
    _: Annotated[CurrentPlatformAdmin, Depends(get_current_platform_admin)],
    db: Annotated[Session, Depends(get_db)],
    file: UploadFile = File(...),
) -> LinkedInLeadImportResult:
    """Import a LinkedIn Lead Gen Form CSV export from Campaign Manager.

    Guaranteed-to-work v1 ingestion path - works with zero LinkedIn API
    partner access. Safe to re-run with overlapping/duplicate exports:
    rows are deduped by linkedin_lead_id.
    """
    content = await file.read()
    return LinkedInLeadImportService(db).import_csv(content)


@router.patch("/{lead_id}", response_model=LinkedInLeadOut)
def update_linkedin_lead(
    lead_id: UUID,
    body: LinkedInLeadUpdate,
    _: Annotated[CurrentPlatformAdmin, Depends(get_current_platform_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> LinkedInLeadOut:
    """Update a lead's triage status and/or owner."""
    lead = LinkedInLeadRepository(db).update_status(lead_id, status=body.status, assigned_to=body.assigned_to)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead
