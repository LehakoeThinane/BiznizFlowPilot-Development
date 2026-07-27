"""Add user presence/status columns - status, status_text, last_seen_at.

Backs manually-chosen presence (online/away/busy/in_meeting/custom) plus a
heartbeat timestamp used to derive online/offline at read time (see
app/services/presence.py). status_text holds free-text custom status
messages like "Out of office, may not respond".

Revision ID: 20260727_37
Revises: 20260723_36
Create Date: 2026-07-27
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260727_37"
down_revision = "20260723_36"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("status", sa.String(length=20), nullable=False, server_default="online"),
    )
    op.add_column("users", sa.Column("status_text", sa.String(length=100), nullable=True))
    op.add_column("users", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(
        "ck_users_status_valid",
        "users",
        "status IN ('online', 'away', 'busy', 'in_meeting', 'custom')",
    )
    op.create_index("ix_users_last_seen_at", "users", ["last_seen_at"])


def downgrade() -> None:
    op.drop_index("ix_users_last_seen_at", table_name="users")
    op.drop_constraint("ck_users_status_valid", "users", type_="check")
    op.drop_column("users", "last_seen_at")
    op.drop_column("users", "status_text")
    op.drop_column("users", "status")
