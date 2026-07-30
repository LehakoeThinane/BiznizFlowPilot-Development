"""Marketing-site public lead-capture API routes - no auth.

🧨 Intentionally unauthenticated: these are how an anonymous marketing-site
visitor becomes a sales lead - trading contact info for a downloadable
guide (guide-leads), or submitting the LinkedIn-ads landing page's own
form (linkedin-form-leads). Unrelated to any Organization/Business - see
app/models/marketing_guide_lead.py and app/models/linkedin_lead.py.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.marketing_guide_lead import MarketingGuideLeadRepository
from app.schemas.linkedin_lead import LinkedInFormLeadCreate
from app.schemas.marketing_guide_lead import MarketingGuideLeadCreate
from app.services.email import send_marketing_guide_lead_email
from app.services.linkedin_leads import LinkedInLeadImportService

router = APIRouter(prefix="/api/v1/marketing", tags=["marketing"])
limiter = Limiter(key_func=get_remote_address)


@router.post("/guide-leads", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def create_guide_lead(
    request: Request, body: MarketingGuideLeadCreate, db: Session = Depends(get_db)
) -> dict[str, bool]:
    MarketingGuideLeadRepository(db).create(
        first_name=body.first_name,
        last_name=body.last_name,
        email=body.email,
        company=body.company,
        guide_slug=body.guide_slug,
        source_page=body.source_page,
        consented_at=datetime.now(timezone.utc),
    )
    try:
        send_marketing_guide_lead_email(
            first_name=body.first_name,
            last_name=body.last_name,
            email=body.email,
            company=body.company,
            guide_slug=body.guide_slug,
        )
    except Exception:
        pass  # email delivery failure is logged inside send_marketing_guide_lead_email/_send

    return {"received": True}


@router.post("/linkedin-form-leads", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def create_linkedin_form_lead(
    request: Request, body: LinkedInFormLeadCreate, db: Session = Depends(get_db)
) -> dict[str, bool]:
    """Submission from the LinkedIn-ads landing page's own form - the
    click-through path, for Sponsored Content ads (native Lead Gen Form
    submissions never hit this route; those arrive via CSV import instead,
    see app/api/linkedin_leads.py)."""
    LinkedInLeadImportService(db).create_from_form(body)
    return {"received": True}
