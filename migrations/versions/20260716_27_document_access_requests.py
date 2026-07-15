"""Add documents.restricted flag and document_access_requests table.

Revision ID: 20260716_27
Revises: 20260716_26
Create Date: 2026-07-16
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260716_27"
down_revision = "20260716_26"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("restricted", sa.Boolean(), nullable=False, server_default="false"),
    )

    op.create_table(
        "document_access_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('pending', 'approved', 'denied')", name="ck_document_access_requests_status"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_document_access_requests_document_id", "document_access_requests", ["document_id"])
    op.create_index("ix_document_access_requests_user_id", "document_access_requests", ["user_id"])
    op.create_index(
        "ix_document_access_requests_doc_user", "document_access_requests", ["document_id", "user_id"], unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_document_access_requests_doc_user", table_name="document_access_requests")
    op.drop_index("ix_document_access_requests_user_id", table_name="document_access_requests")
    op.drop_index("ix_document_access_requests_document_id", table_name="document_access_requests")
    op.drop_table("document_access_requests")
    op.drop_column("documents", "restricted")
