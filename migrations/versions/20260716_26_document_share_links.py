"""Add document_share_links table for expiring external share links.

Revision ID: 20260716_26
Revises: 20260715_25
Create Date: 2026-07-16
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260716_26"
down_revision = "20260715_25"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_share_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token"),
    )
    op.create_index("ix_document_share_links_document_id", "document_share_links", ["document_id"])
    op.create_index("ix_document_share_links_token", "document_share_links", ["token"])


def downgrade() -> None:
    op.drop_index("ix_document_share_links_token", table_name="document_share_links")
    op.drop_index("ix_document_share_links_document_id", table_name="document_share_links")
    op.drop_table("document_share_links")
