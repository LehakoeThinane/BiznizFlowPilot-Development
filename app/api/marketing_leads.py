"""Marketing-site gated guide download API route - public (no auth).

🧨 Intentionally unauthenticated: this is how an anonymous marketing-site
visitor trades contact info for a downloadable guide, becoming a sales
lead. Unrelated to any Organization/Business - see app/models/marketing_guide_lead.py.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.marketing_guide_lead import MarketingGuideLeadRepository
from app.schemas.marketing_guide_lead import MarketingGuideLeadCreate
from app.services.email import send_marketing_guide_lead_email

router = APIRouter(prefix="/api/v1/marketing/guide-leads", tags=["marketing"])
limiter = Limiter(key_func=get_remote_address)


@router.post("", status_code=status.HTTP_201_CREATED)
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
