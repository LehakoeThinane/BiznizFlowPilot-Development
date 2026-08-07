"""Add website chat widget support: conversations.source/ai_active columns,
messages.is_ai_reply (visitor and AI messages share one system User as
sender - this is what tells them apart when rebuilding LLM history), and
the website_chat_sessions table mapping an anonymous browser session token
to its Conversation (see app/services/website_chat.py).

Revision ID: 20260806_46
Revises: 20260806_45
Create Date: 2026-08-06
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260806_46"
down_revision = "20260806_45"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("source", sa.String(length=20), nullable=False, server_default="internal"),
    )
    op.add_column(
        "conversations",
        sa.Column("ai_active", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.add_column(
        "messages",
        sa.Column("is_ai_reply", sa.Boolean(), nullable=False, server_default="false"),
    )

    op.create_table(
        "website_chat_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_website_chat_sessions_token", "website_chat_sessions", ["token"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_website_chat_sessions_token", "website_chat_sessions")
    op.drop_table("website_chat_sessions")
    op.drop_column("messages", "is_ai_reply")
    op.drop_column("conversations", "ai_active")
    op.drop_column("conversations", "source")
