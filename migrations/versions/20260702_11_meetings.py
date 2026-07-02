"""Add meetings and meeting_participants tables for calendar scheduling and
Agora-backed voice/video calls; extend notification_type with 'meeting'.

Revision ID: 20260702_11
Revises: 20260702_10
Create Date: 2026-07-02
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260702_11"
down_revision = "20260702_10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'meeting'")

    op.create_table(
        "meetings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("business_id", sa.UUID(), nullable=False),
        sa.Column("organizer_id", sa.UUID(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("call_type", sa.String(length=20), nullable=False, server_default=sa.text("'video'")),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'scheduled'")),
        sa.Column("agora_channel_name", sa.String(length=100), nullable=False),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organizer_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agora_channel_name", name="uq_meetings_agora_channel_name"),
        sa.CheckConstraint("call_type IN ('voice', 'video')", name="ck_meetings_call_type_valid"),
        sa.CheckConstraint(
            "status IN ('scheduled', 'in_progress', 'completed', 'cancelled')",
            name="ck_meetings_status_valid",
        ),
    )
    op.create_index(op.f("ix_meetings_business_id"), "meetings", ["business_id"], unique=False)
    op.create_index("ix_meetings_biz_start", "meetings", ["business_id", "start_time"], unique=False)
    op.create_index("ix_meetings_biz_status", "meetings", ["business_id", "status"], unique=False)

    op.create_table(
        "meeting_participants",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("meeting_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("response_status", sa.String(length=20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("meeting_id", "user_id", name="uq_meeting_participant"),
        sa.CheckConstraint(
            "response_status IN ('pending', 'accepted', 'declined')",
            name="ck_meeting_participants_response_status_valid",
        ),
    )
    op.create_index(op.f("ix_meeting_participants_meeting_id"), "meeting_participants", ["meeting_id"], unique=False)
    op.create_index("ix_meeting_participants_user", "meeting_participants", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_meeting_participants_user", table_name="meeting_participants")
    op.drop_index(op.f("ix_meeting_participants_meeting_id"), table_name="meeting_participants")
    op.drop_table("meeting_participants")

    op.drop_index("ix_meetings_biz_status", table_name="meetings")
    op.drop_index("ix_meetings_biz_start", table_name="meetings")
    op.drop_index(op.f("ix_meetings_business_id"), table_name="meetings")
    op.drop_table("meetings")

    # Postgres cannot remove an enum value; 'meeting' is left in notification_type on downgrade.
