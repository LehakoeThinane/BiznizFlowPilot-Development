"""Platform (vendor staff) schemas - auth, admin management, org provisioning."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ── Auth ─────────────────────────────────────────────────────────────────────


class PlatformLoginRequest(BaseModel):
    """Platform admin login request."""

    email: EmailStr
    password: str


class PlatformTokenResponse(BaseModel):
    """Platform JWT token response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class CurrentPlatformAdmin(BaseModel):
    """Current authenticated platform admin (from JWT, plus DB-resolved context)."""

    platform_admin_id: UUID
    email: str
    full_name: str
    platform_role: str
    impersonation_allowed: bool


# ── Platform admin management ────────────────────────────────────────────────


class PlatformAdminCreate(BaseModel):
    """Create a new platform admin (requires an existing admin/super_admin)."""

    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str = Field(..., min_length=1, max_length=200)
    platform_role: str = Field(default="support", pattern=r"^(support|billing_ops|admin|super_admin)$")
    impersonation_allowed: bool = False


class PlatformAdminResponse(BaseModel):
    """Platform admin summary."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    full_name: str
    platform_role: str
    is_active: bool
    impersonation_allowed: bool
    last_login_at: str | None = None


# ── Organization provisioning ────────────────────────────────────────────────


class OrganizationProvisionRequest(BaseModel):
    """Provision a brand-new client Organization + first subsidiary.

    No owner password is collected here — the client's owner sets their own
    credentials by accepting the invite email sent on provisioning.
    """

    org_name: str = Field(..., min_length=1, max_length=255)
    billing_email: EmailStr
    owner_email: EmailStr
    subsidiary_name: str | None = None
    primary_domain: str | None = None
    plan_tier: str = Field(default="trial", pattern=r"^(trial|starter|growth|professional|enterprise|legacy)$")


class OrganizationAdminUpdate(BaseModel):
    """Platform-side organization update (billing/plan fields tenant users can't touch)."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    plan_tier: str | None = Field(default=None, pattern=r"^(trial|starter|growth|professional|enterprise|legacy)$")
    subscription_status: str | None = Field(
        default=None, pattern=r"^(trial|active|past_due|suspended|cancelled)$"
    )
    seats_included: int | None = None


class OrganizationAdminResponse(BaseModel):
    """Organization detail as seen by platform admins."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    billing_email: str
    plan_tier: str
    subscription_status: str
    seats_included: int | None
    subsidiary_count: int = 0
    user_count: int = 0


class OrganizationAdminListResponse(BaseModel):
    """Paginated list of organizations."""

    total: int
    items: list[OrganizationAdminResponse]


# ── Per-organization custom SMTP sender (meeting invites, etc.) ──────────────

class OrganizationEmailConfigUpdate(BaseModel):
    """Set/replace an organization's custom SMTP sender.

    smtp_password is write-only and optional: omit or pass null to leave the
    already-stored (encrypted) password unchanged - only send it when
    actually replacing it.
    """

    smtp_host: str = Field(..., min_length=1, max_length=255)
    smtp_port: int = Field(..., ge=1, le=65535)
    smtp_username: str = Field(..., min_length=1, max_length=255)
    smtp_password: str | None = Field(default=None, min_length=1)
    smtp_from_email: EmailStr
    smtp_from_name: str = Field(..., min_length=1, max_length=255)


class OrganizationEmailConfigResponse(BaseModel):
    """Never echoes the real password - only whether one is stored."""

    model_config = ConfigDict(from_attributes=True)

    smtp_host: str | None
    smtp_port: int | None
    smtp_username: str | None
    smtp_password_set: bool
    smtp_from_email: str | None
    smtp_from_name: str | None
