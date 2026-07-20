"""Add message_attachments, polls, poll_options, poll_votes tables, and
extend messages with message_type + nullable references (attachment,
shared customer/meeting, poll, sticker) for the chat attachment menu.

Revision ID: 20260719_31
Revises: 20260716_30
Create Date: 2026-07-19
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260719_31"
down_revision = "20260716_30"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "message_attachments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("business_id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("uploaded_by", sa.UUID(), nullable=True),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index(op.f("ix_message_attachments_business_id"), "message_attachments", ["business_id"], unique=False)
    op.create_index(op.f("ix_message_attachments_conversation_id"), "message_attachments", ["conversation_id"], unique=False)

    op.create_table(
        "polls",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("business_id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("question", sa.String(500), nullable=False),
        sa.Column("allow_multiple", sa.Boolean(), nullable=False, server_default="false"),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_polls_business_id"), "polls", ["business_id"], unique=False)
    op.create_index(op.f("ix_polls_conversation_id"), "polls", ["conversation_id"], unique=False)

    op.create_table(
        "poll_options",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("poll_id", sa.UUID(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["poll_id"], ["polls.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_poll_options_poll_id"), "poll_options", ["poll_id"], unique=False)

    op.create_table(
        "poll_votes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("poll_id", sa.UUID(), nullable=False),
        sa.Column("option_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["poll_id"], ["polls.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["option_id"], ["poll_options.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("option_id", "user_id", name="uq_poll_vote_option_user"),
    )
    op.create_index(op.f("ix_poll_votes_poll_id"), "poll_votes", ["poll_id"], unique=False)
    op.create_index(op.f("ix_poll_votes_option_id"), "poll_votes", ["option_id"], unique=False)

    op.alter_column("messages", "content", existing_type=sa.Text(), nullable=True)
    op.add_column("messages", sa.Column("message_type", sa.String(20), nullable=False, server_default="text"))
    op.add_column("messages", sa.Column("attachment_id", sa.UUID(), nullable=True))
    op.add_column("messages", sa.Column("shared_customer_id", sa.UUID(), nullable=True))
    op.add_column("messages", sa.Column("shared_meeting_id", sa.UUID(), nullable=True))
    op.add_column("messages", sa.Column("poll_id", sa.UUID(), nullable=True))
    op.add_column("messages", sa.Column("sticker_key", sa.String(50), nullable=True))
    op.create_foreign_key(
        "fk_messages_attachment_id", "messages", "message_attachments", ["attachment_id"], ["id"], ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_messages_shared_customer_id", "messages", "customers", ["shared_customer_id"], ["id"], ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_messages_shared_meeting_id", "messages", "meetings", ["shared_meeting_id"], ["id"], ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_messages_poll_id", "messages", "polls", ["poll_id"], ["id"], ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_messages_poll_id", "messages", type_="foreignkey")
    op.drop_constraint("fk_messages_shared_meeting_id", "messages", type_="foreignkey")
    op.drop_constraint("fk_messages_shared_customer_id", "messages", type_="foreignkey")
    op.drop_constraint("fk_messages_attachment_id", "messages", type_="foreignkey")
    op.drop_column("messages", "sticker_key")
    op.drop_column("messages", "poll_id")
    op.drop_column("messages", "shared_meeting_id")
    op.drop_column("messages", "shared_customer_id")
    op.drop_column("messages", "attachment_id")
    op.drop_column("messages", "message_type")
    op.alter_column("messages", "content", existing_type=sa.Text(), nullable=False)

    op.drop_index(op.f("ix_poll_votes_option_id"), table_name="poll_votes")
    op.drop_index(op.f("ix_poll_votes_poll_id"), table_name="poll_votes")
    op.drop_table("poll_votes")

    op.drop_index(op.f("ix_poll_options_poll_id"), table_name="poll_options")
    op.drop_table("poll_options")

    op.drop_index(op.f("ix_polls_conversation_id"), table_name="polls")
    op.drop_index(op.f("ix_polls_business_id"), table_name="polls")
    op.drop_table("polls")

    op.drop_index(op.f("ix_message_attachments_conversation_id"), table_name="message_attachments")
    op.drop_index(op.f("ix_message_attachments_business_id"), table_name="message_attachments")
    op.drop_table("message_attachments")
