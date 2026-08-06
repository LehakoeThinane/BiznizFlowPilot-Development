"""Add email_theme/email_background display-preference columns to
user_email_accounts - scoped to the Email page only (not an app-wide
theme), and independent of whether IMAP/SMTP is actually configured on
the row (both fields are optional prefs, not mailbox config).

Plain VARCHAR + CHECK constraint for email_theme, not a native Postgres
enum - this exact codebase just had a production incident this session
from forgetting to migrate a new native-enum value (notification_type)
before deploying code that wrote it. Matches the existing
users.status CHECK-constraint convention (20260727_37_user_presence_status.py).

Revision ID: 20260805_44
Revises: 20260805_43
Create Date: 2026-08-05
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260805_44"
down_revision = "20260805_43"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_email_accounts",
        sa.Column("email_theme", sa.String(length=10), nullable=False, server_default="dark"),
    )
    op.add_column(
        "user_email_accounts",
        sa.Column("email_background", sa.String(length=50), nullable=True),
    )
    op.create_check_constraint(
        "ck_user_email_accounts_theme_valid",
        "user_email_accounts",
        "email_theme IN ('light', 'dark')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_user_email_accounts_theme_valid", "user_email_accounts", type_="check")
    op.drop_column("user_email_accounts", "email_background")
    op.drop_column("user_email_accounts", "email_theme")
