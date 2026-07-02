"""Convert events.event_type from free text to enum.

Revision ID: 20260420_02
Revises: 20260420_01
Create Date: 2026-04-20
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260420_02"
down_revision = "20260420_01"
branch_labels = None
depends_on = None


event_type_enum = sa.Enum(
    "lead_created",
    "lead_status_changed",
    "task_created",
    "task_assigned",
    "task_completed",
    "workflow_triggered",
    "custom",
    name="event_type_enum",
)


def upgrade() -> None:
    """Normalize existing event types and convert column to enum."""
    bind = op.get_bind()
    event_type_enum.create(bind, checkfirst=True)

    allowed = (
        "lead_created",
        "lead_status_changed",
        "task_created",
        "task_assigned",
        "task_completed",
        "workflow_triggered",
        "custom",
    )
    allowed_sql = ", ".join(f"'{value}'" for value in allowed)
    op.execute(f"UPDATE events SET event_type = 'custom' WHERE event_type NOT IN ({allowed_sql})")

    op.alter_column(
        "events",
        "event_type",
        existing_type=sa.String(length=100),
        type_=event_type_enum,
        postgresql_using="event_type::event_type_enum",
    )


def downgrade() -> None:
    """Revert event_type back to free-text string."""
    op.alter_column(
        "events",
        "event_type",
        existing_type=event_type_enum,
        type_=sa.String(length=100),
        postgresql_using="event_type::text",
    )

    bind = op.get_bind()
    event_type_enum.drop(bind, checkfirst=True)
