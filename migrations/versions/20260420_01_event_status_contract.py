"""Replace events.processed boolean with status lifecycle fields.

Revision ID: 20260420_01
Revises: 20260420_00
Create Date: 2026-04-20
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260420_01"
down_revision = "20260420_00"
branch_labels = None
depends_on = None


event_status = sa.Enum("pending", "processing", "processed", "failed", name="event_status")


def upgrade() -> None:
    """Migrate events table to status lifecycle fields."""
    bind = op.get_bind()
    event_status.create(bind, checkfirst=True)

    op.add_column(
        "events",
        sa.Column("status", event_status, nullable=False, server_default="pending"),
    )
    op.add_column("events", sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("events", sa.Column("claimed_by", sa.String(length=255), nullable=True))

    op.execute("UPDATE events SET status = 'processed' WHERE processed IS TRUE")
    op.execute("UPDATE events SET status = 'pending' WHERE processed IS FALSE OR processed IS NULL")

    op.create_index(op.f("ix_events_status"), "events", ["status"], unique=False)
    op.create_index(op.f("ix_events_locked_at"), "events", ["locked_at"], unique=False)
    op.create_index(op.f("ix_events_claimed_by"), "events", ["claimed_by"], unique=False)
    op.create_index(op.f("ix_events_business_id_status"), "events", ["business_id", "status"], unique=False)

    op.drop_column("events", "processed")
    op.alter_column("events", "status", server_default=None)


def downgrade() -> None:
    """Revert status lifecycle fields back to processed boolean."""
    op.add_column(
        "events",
        sa.Column("processed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.execute("UPDATE events SET processed = (status = 'processed')")

    op.drop_index(op.f("ix_events_claimed_by"), table_name="events")
    op.drop_index(op.f("ix_events_locked_at"), table_name="events")
    op.drop_index(op.f("ix_events_status"), table_name="events")
    op.drop_index(op.f("ix_events_business_id_status"), table_name="events")

    op.drop_column("events", "claimed_by")
    op.drop_column("events", "locked_at")
    op.drop_column("events", "status")

    bind = op.get_bind()
    event_status.drop(bind, checkfirst=True)
