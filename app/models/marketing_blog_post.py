"""MarketingBlogPost model - MM Nexus's own marketing blog content, authored
via the drag-and-drop CMS, distinct from any tenant/business data.

Draft-vs-published is a real status column (unlike the document editor's
checkout-based inference) because there's no "checked out by" concept here -
any marketing_cms_admin can pick up any draft.
"""

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB

from app.models.base import BaseModel


class MarketingBlogPost(BaseModel):
    """A blog post, either an unpublished draft or a published, live post."""

    __tablename__ = "marketing_blog_posts"
    __table_args__ = (
        CheckConstraint("status IN ('draft', 'published')", name="ck_marketing_blog_posts_status_valid"),
    )

    slug = Column(String(255), nullable=False, index=True, doc="URL slug - also the .md filename")
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    author = Column(String(200), nullable=False, server_default="MM Nexus")
    cover_image_url = Column(String(1000), nullable=True)

    content_blocks = Column(
        JSONB,
        nullable=False,
        server_default="[]",
        doc="Raw BlockNote block array - the re-editable source of truth",
    )

    status = Column(
        String(20),
        nullable=False,
        server_default="draft",
        index=True,
        doc="draft | published - enforced at the database level, see ck_marketing_blog_posts_status_valid",
    )

    published_at = Column(DateTime(timezone=True), nullable=True, index=True)

    github_commit_sha = Column(
        String(40),
        nullable=True,
        doc="Commit SHA of the last successful publish - drives publish idempotency",
    )

    auto_publish_ready = Column(
        Boolean,
        nullable=False,
        server_default="false",
        doc="Human has explicitly queued this draft for the daily autopublish task to pick up",
    )
    pending_markdown_body = Column(
        Text,
        nullable=True,
        doc=(
            "Markdown snapshot computed client-side (same blocksToMarkdownLossy() the manual "
            "Publish button uses) at the moment a draft was scheduled or AI-generated - the "
            "daily autopublish task has no browser/BlockNote available, so it publishes this "
            "stored snapshot directly rather than deriving markdown server-side."
        ),
    )

    created_by = Column(Uuid, ForeignKey("marketing_cms_admins.id", ondelete="SET NULL"), nullable=True)
    updated_by = Column(Uuid, ForeignKey("marketing_cms_admins.id", ondelete="SET NULL"), nullable=True)

    def __repr__(self) -> str:
        """String representation."""
        return f"<MarketingBlogPost id={self.id} slug='{self.slug}' status='{self.status}'>"
