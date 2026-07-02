"""Add self-referential manager_id to employees for org-chart reporting lines.

Revision ID: 20260702_10
Revises: 20260702_09
Create Date: 2026-07-02
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260702_10"
down_revision = "20260702_09"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("employees", sa.Column("manager_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_employees_manager_id", "employees", "employees", ["manager_id"], ["id"], ondelete="SET NULL"
    )
    op.create_index(op.f("ix_employees_manager"), "employees", ["manager_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_employees_manager"), table_name="employees")
    op.drop_constraint("fk_employees_manager_id", "employees", type_="foreignkey")
    op.drop_column("employees", "manager_id")
