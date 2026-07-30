"""LinkedIn lead ingestion - CSV import (from a Campaign Manager export)
and the public landing-page form both funnel through here, sharing the
same dedupe-by-linkedin_lead_id and staff-notification tail. See
app/models/linkedin_lead.py for why these two paths (plus a future
api_poll path) all write to one table.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.repositories.linkedin_lead import LinkedInLeadRepository
from app.schemas.linkedin_lead import LinkedInFormLeadCreate, LinkedInLeadCSVRow, LinkedInLeadImportResult
from app.services.email import send_linkedin_lead_email

# Maps our internal field names onto the column headers LinkedIn's Lead Gen
# Form CSV export actually uses. NOT yet confirmed against a real export -
# see the plan's verification step. Update this mapping once a real file
# is available, rather than the schema itself.
_CSV_HEADER_MAP = {
    "Lead ID": "linkedin_lead_id",
    "First Name": "first_name",
    "Last Name": "last_name",
    "Email Address": "email",
    "Company Name": "company",
    "Job Title": "job_title",
    "Phone Number": "phone",
    "Campaign Name": "campaign_name",
    "Form Name": "form_name",
    "Submitted At": "submitted_at",
}


class LinkedInLeadImportService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = LinkedInLeadRepository(db)

    def import_csv(self, content: bytes) -> LinkedInLeadImportResult:
        text = content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))

        imported = 0
        skipped_duplicates = 0
        errors: list[str] = []

        for row_number, raw_row in enumerate(reader, start=2):  # header is row 1
            # CSV cells are always strings - a blank cell is "", not absent.
            # Normalize blanks to None so optional fields validate correctly
            # (an empty string isn't a valid datetime, for example) while
            # required-but-blank fields still fail validation as intended.
            mapped = {
                _CSV_HEADER_MAP.get(k, k): (v.strip() or None) if isinstance(v, str) else v
                for k, v in raw_row.items() if k
            }
            try:
                row = LinkedInLeadCSVRow.model_validate(mapped)
            except ValidationError as exc:
                errors.append(f"Row {row_number}: {exc.errors()[0]['msg'] if exc.errors() else exc}")
                continue

            if self.repo.get_by_linkedin_lead_id(row.linkedin_lead_id):
                skipped_duplicates += 1
                continue

            self.repo.create(
                linkedin_lead_id=row.linkedin_lead_id,
                first_name=row.first_name,
                last_name=row.last_name,
                email=row.email,
                company=row.company,
                job_title=row.job_title,
                phone=row.phone,
                campaign_name=row.campaign_name,
                form_name=row.form_name,
                submitted_at=row.submitted_at,
                ingestion_source="csv_import",
            )
            imported += 1

            try:
                send_linkedin_lead_email(
                    first_name=row.first_name, last_name=row.last_name, email=row.email,
                    company=row.company, job_title=row.job_title, campaign_name=row.campaign_name,
                )
            except Exception:
                pass  # delivery failure is logged inside send_linkedin_lead_email/_send

        return LinkedInLeadImportResult(imported=imported, skipped_duplicates=skipped_duplicates, errors=errors)

    def import_api_payload(self, payload: dict) -> bool:
        """Import one lead from the (currently stubbed) Lead Sync API poll.

        Returns True if a new row was created, False if it was a duplicate
        (already-seen linkedin_lead_id) skipped. Shares the exact same
        validate -> dedupe -> create -> notify pipeline as import_csv,
        just fed from an API payload dict instead of a CSV row - see
        app/integrations/linkedin.py for why this path is currently inert.
        """
        try:
            row = LinkedInLeadCSVRow.model_validate(payload)
        except ValidationError:
            return False

        if self.repo.get_by_linkedin_lead_id(row.linkedin_lead_id):
            return False

        self.repo.create(
            linkedin_lead_id=row.linkedin_lead_id,
            first_name=row.first_name,
            last_name=row.last_name,
            email=row.email,
            company=row.company,
            job_title=row.job_title,
            phone=row.phone,
            campaign_name=row.campaign_name,
            form_name=row.form_name,
            submitted_at=row.submitted_at,
            ingestion_source="api_poll",
        )
        try:
            send_linkedin_lead_email(
                first_name=row.first_name, last_name=row.last_name, email=row.email,
                company=row.company, job_title=row.job_title, campaign_name=row.campaign_name,
            )
        except Exception:
            pass
        return True

    def create_from_form(self, body: LinkedInFormLeadCreate) -> None:
        self.repo.create(
            linkedin_lead_id=f"landing_page:{uuid4()}",
            first_name=body.first_name,
            last_name=body.last_name,
            email=body.email,
            company=body.company,
            job_title=body.job_title,
            phone=body.phone,
            utm_source=body.utm_source,
            utm_medium=body.utm_medium,
            utm_campaign=body.utm_campaign,
            submitted_at=datetime.now(timezone.utc),
            ingestion_source="landing_page",
        )
        try:
            send_linkedin_lead_email(
                first_name=body.first_name, last_name=body.last_name, email=body.email,
                company=body.company, job_title=body.job_title, campaign_name=body.utm_campaign,
            )
        except Exception:
            pass
