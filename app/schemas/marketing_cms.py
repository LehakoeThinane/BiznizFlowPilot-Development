"""Marketing blog CMS schemas - auth and blog post shapes.

Fully separate from app/schemas/platform.py - this is MM Nexus's own
marketing content tooling, not vendor-staff/tenant-provisioning tooling.
"""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ── Auth ─────────────────────────────────────────────────────────────────────


class MarketingCmsLoginRequest(BaseModel):
    """Marketing CMS admin login request."""

    email: EmailStr
    password: str


class MarketingCmsTokenResponse(BaseModel):
    """Marketing CMS JWT token response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class CurrentMarketingCmsAdmin(BaseModel):
    """Current authenticated marketing CMS admin (from JWT, DB-resolved)."""

    marketing_cms_admin_id: UUID
    email: str
    full_name: str


# ── Blog posts ───────────────────────────────────────────────────────────────


class BlogPostCreate(BaseModel):
    """Create a new draft post."""

    title: str = Field(default="Untitled post", min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=255, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class BlogPostUpdate(BaseModel):
    """Autosave payload - all fields optional, only sent fields are changed."""

    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    author: Optional[str] = Field(default=None, min_length=1, max_length=200)
    cover_image_url: Optional[str] = Field(default=None, max_length=1000)
    content_blocks: Optional[list[dict[str, Any]]] = None


class BlogPostResponse(BaseModel):
    """Full post detail, including editable block content."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    slug: str
    title: str
    description: str
    author: str
    cover_image_url: Optional[str]
    content_blocks: list[dict[str, Any]]
    status: str
    published_at: Optional[datetime]
    github_commit_sha: Optional[str]
    created_at: datetime
    updated_at: datetime


class BlogPostListItem(BaseModel):
    """Summary shape for the post list view - omits content_blocks."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    slug: str
    title: str
    status: str
    published_at: Optional[datetime]
    updated_at: datetime


class BlogPostListResponse(BaseModel):
    items: list[BlogPostListItem]


class BlogGenerateRequest(BaseModel):
    """AI-assist request - draft body content for a topic."""

    topic: str = Field(..., min_length=1, max_length=500)
    tone: Optional[str] = Field(default=None, max_length=100)


class BlogGenerateResponse(BaseModel):
    """Markdown text, parsed into blocks client-side for editing."""

    markdown: str


class BlogPublishRequest(BaseModel):
    """Publish payload - markdown_body is computed client-side from the
    current BlockNote blocks via editor.blocksToMarkdownLossy()."""

    markdown_body: str = Field(..., min_length=1)


class BlogPublishResponse(BaseModel):
    published: bool
    github_commit_sha: Optional[str] = None
