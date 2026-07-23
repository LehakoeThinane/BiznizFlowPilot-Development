"""Marketing-site gated guide download schemas."""

from pydantic import BaseModel, EmailStr, Field, field_validator


class MarketingGuideLeadCreate(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=255)
    last_name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    company: str = Field(..., min_length=1, max_length=255)
    guide_slug: str = Field(..., min_length=1, max_length=100)
    source_page: str | None = Field(default=None, max_length=255)
    consented: bool

    @field_validator("consented")
    @classmethod
    def _must_consent(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Consent is required to download a guide.")
        return value
