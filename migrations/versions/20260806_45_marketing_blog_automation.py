"""Add marketing_blog_topics table and auto_publish_ready/pending_markdown_body
columns to marketing_blog_posts - backs the daily blog autopublish task's
topic backlog and its client-computed-markdown snapshot for both
human-scheduled and AI-generated drafts (no server-side BlockNote
blocks-to-markdown converter exists, so markdown is captured client-side
at schedule/generate time and stored here for the task to publish later).

Revision ID: 20260806_45
Revises: 20260805_44
Create Date: 2026-08-06
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260806_45"
down_revision = "20260805_44"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "marketing_blog_topics",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("topic", sa.Text(), nullable=False),
        sa.Column("tone", sa.String(length=100), nullable=True),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_marketing_blog_topics_used_at", "marketing_blog_topics", ["used_at"])

    op.add_column(
        "marketing_blog_posts",
        sa.Column("auto_publish_ready", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "marketing_blog_posts",
        sa.Column("pending_markdown_body", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("marketing_blog_posts", "pending_markdown_body")
    op.drop_column("marketing_blog_posts", "auto_publish_ready")
    op.drop_index("ix_marketing_blog_topics_used_at", "marketing_blog_topics")
    op.drop_table("marketing_blog_topics")
