"""Request schemas for the public free-trial signup endpoints."""

from pydantic import BaseModel, EmailStr, Field


class TrialSignupRequest(BaseModel):
    """Request body for POST /signup/trial (email/password)."""

    organization_name: str = Field(..., min_length=1, max_length=255)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8)


class TrialSignupGoogleRequest(BaseModel):
    """Request body for POST /signup/trial/google."""

    organization_name: str = Field(..., min_length=1, max_length=255)
    credential: str = Field(..., min_length=1)
