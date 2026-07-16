"""Add folders table (nested, business-scoped containers for documents).

Revision ID: 20260716_29
Revises: 20260716_28
Create Date: 2026-07-16
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260716_29"
down_revision = "20260716_28"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "folders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("parent_folder_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_folder_id"], ["folders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_folders_business_id", "folders", ["business_id"])
    op.create_index("ix_folders_business_parent", "folders", ["business_id", "parent_folder_id"])


def downgrade() -> None:
    op.drop_index("ix_folders_business_parent", table_name="folders")
    op.drop_index("ix_folders_business_id", table_name="folders")
    op.drop_table("folders")
