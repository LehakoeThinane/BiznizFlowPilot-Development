"""Add marketing_cms_admins and marketing_blog_posts tables - a fully
separate, non-tenant auth/content boundary for MM Nexus's own marketing blog
CMS (drag-and-drop draft/publish editor), distinct from both tenant `users`
and `platform_admins`.

Revision ID: 20260803_40
Revises: 20260729_39
Create Date: 2026-08-03
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260803_40"
down_revision = "20260729_39"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "marketing_cms_admins",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("failed_login_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_marketing_cms_admins_email", "marketing_cms_admins", ["email"], unique=True
    )

    op.create_table(
        "marketing_blog_posts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("author", sa.String(length=200), server_default="MM Nexus", nullable=False),
        sa.Column("cover_image_url", sa.String(length=1000), nullable=True),
        sa.Column(
            "content_blocks",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("status", sa.String(length=20), server_default="draft", nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("github_commit_sha", sa.String(length=40), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.CheckConstraint("status IN ('draft', 'published')", name="ck_marketing_blog_posts_status_valid"),
        sa.ForeignKeyConstraint(["created_by"], ["marketing_cms_admins.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by"], ["marketing_cms_admins.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_marketing_blog_posts_slug", "marketing_blog_posts", ["slug"], unique=True
    )
    op.create_index("ix_marketing_blog_posts_status", "marketing_blog_posts", ["status"])
    op.create_index("ix_marketing_blog_posts_published_at", "marketing_blog_posts", ["published_at"])


def downgrade() -> None:
    op.drop_index("ix_marketing_blog_posts_published_at", table_name="marketing_blog_posts")
    op.drop_index("ix_marketing_blog_posts_status", table_name="marketing_blog_posts")
    op.drop_index("ix_marketing_blog_posts_slug", table_name="marketing_blog_posts")
    op.drop_table("marketing_blog_posts")
    op.drop_index("ix_marketing_cms_admins_email", table_name="marketing_cms_admins")
    op.drop_table("marketing_cms_admins")
