"""Add per-organization custom SMTP sender columns and a
meeting_external_participants table, for meeting invites by raw email
address with token-based accept/decline (no login required).

Revision ID: 20260722_33
Revises: 20260721_32
Create Date: 2026-07-22
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260722_33"
down_revision = "20260721_32"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("smtp_host", sa.String(255), nullable=True))
    op.add_column("organizations", sa.Column("smtp_port", sa.Integer(), nullable=True))
    op.add_column("organizations", sa.Column("smtp_username", sa.String(255), nullable=True))
    op.add_column("organizations", sa.Column("smtp_password_encrypted", sa.String(500), nullable=True))
    op.add_column("organizations", sa.Column("smtp_from_email", sa.String(255), nullable=True))
    op.add_column("organizations", sa.Column("smtp_from_name", sa.String(255), nullable=True))

    op.create_table(
        "meeting_external_participants",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("meeting_id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("token_hash", sa.String(128), nullable=False),
        sa.Column("response_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("meeting_id", "email", name="uq_meeting_external_participants_meeting_email"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        "ix_meeting_external_participants_meeting",
        "meeting_external_participants",
        ["meeting_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_meeting_external_participants_meeting", table_name="meeting_external_participants")
    op.drop_table("meeting_external_participants")

    op.drop_column("organizations", "smtp_from_name")
    op.drop_column("organizations", "smtp_from_email")
    op.drop_column("organizations", "smtp_password_encrypted")
    op.drop_column("organizations", "smtp_username")
    op.drop_column("organizations", "smtp_port")
    op.drop_column("organizations", "smtp_host")
