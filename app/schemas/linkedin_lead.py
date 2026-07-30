"""LinkedIn lead-generation schemas - CSV import, the public landing-page
form, and the platform-admin status/routing update."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LinkedInLeadCSVRow(BaseModel):
    """One parsed row from a LinkedIn Lead Gen Form CSV export.

    Field names are our own internal names, not LinkedIn's literal export
    column headers - app/services/linkedin_leads.py maps LinkedIn's actual
    header row onto these before validation. Not yet confirmed against a
    real export (see the plan's verification section) - revisit the header
    mapping once a real CSV file is available.
    """

    linkedin_lead_id: str = Field(..., min_length=1, max_length=255)
    first_name: str = Field(..., min_length=1, max_length=255)
    last_name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    company: str | None = Field(default=None, max_length=255)
    job_title: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    campaign_name: str | None = Field(default=None, max_length=255)
    form_name: str | None = Field(default=None, max_length=255)
    submitted_at: datetime | None = None


class LinkedInLeadImportResult(BaseModel):
    imported: int
    skipped_duplicates: int
    errors: list[str] = Field(default_factory=list)


class LinkedInFormLeadCreate(BaseModel):
    """Body for the public landing-page lead form."""

    first_name: str = Field(..., min_length=1, max_length=255)
    last_name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    company: str | None = Field(default=None, max_length=255)
    job_title: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    utm_source: str | None = Field(default=None, max_length=255)
    utm_medium: str | None = Field(default=None, max_length=255)
    utm_campaign: str | None = Field(default=None, max_length=255)


class LinkedInLeadUpdate(BaseModel):
    """Body for PATCH /platform/v1/linkedin-leads/{id}."""

    status: str | None = Field(None, pattern="^(new|contacted|qualified|disqualified)$")
    assigned_to: str | None = Field(None, max_length=255)


class LinkedInLeadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    linkedin_lead_id: str
    campaign_name: str | None
    form_name: str | None
    first_name: str
    last_name: str
    email: str
    company: str | None
    job_title: str | None
    phone: str | None
    utm_source: str | None
    utm_medium: str | None
    utm_campaign: str | None
    ingestion_source: str
    status: str
    assigned_to: str | None
    submitted_at: datetime | None
