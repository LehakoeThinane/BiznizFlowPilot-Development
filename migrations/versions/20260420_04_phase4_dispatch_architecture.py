"""Phase 4 dispatcher architecture: definitions, lifecycle, and idempotent runs.

Revision ID: 20260420_04
Revises: 20260420_03
Create Date: 2026-04-20
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260420_04"
down_revision = "20260420_03"
branch_labels = None
depends_on = None


workflow_run_status = sa.Enum(
    "queued",
    "running",
    "completed",
    "failed",
    name="workflow_run_status",
)


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return inspector.has_table(table_name)


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(table_name):
        return False
    columns = inspector.get_columns(table_name)
    return any(column["name"] == column_name for column in columns)


def _index_exists(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(table_name):
        return False
    indexes = inspector.get_indexes(table_name)
    return any(index["name"] == index_name for index in indexes)


def upgrade() -> None:
    """Apply phase-4 workflow dispatch schema changes."""
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        op.execute("ALTER TYPE event_status RENAME VALUE 'processing' TO 'claimed'")
        op.execute("ALTER TYPE event_status RENAME VALUE 'processed' TO 'dispatched'")

    if is_postgres:
        workflow_run_status.create(bind, checkfirst=True)

    if not _table_exists("workflow_definitions"):
        op.create_table(
            "workflow_definitions",
            sa.Column("business_id", sa.UUID(), nullable=False),
            sa.Column("event_type", sa.String(length=100), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("name", sa.String(length=255), nullable=False, server_default="Workflow Definition"),
            sa.Column("conditions", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("config", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("workflow_id", sa.UUID(), nullable=True),
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_workflow_definitions_business_id"), "workflow_definitions", ["business_id"], unique=False)
        op.create_index(op.f("ix_workflow_definitions_event_type"), "workflow_definitions", ["event_type"], unique=False)
        op.create_index(op.f("ix_workflow_definitions_is_active"), "workflow_definitions", ["is_active"], unique=False)
        op.create_index(op.f("ix_workflow_definitions_workflow_id"), "workflow_definitions", ["workflow_id"], unique=False)

    if not _table_exists("workflow_runs"):
        return

    if _column_exists("workflow_runs", "workflow_id"):
        op.alter_column("workflow_runs", "workflow_id", existing_type=sa.UUID(), nullable=True)

    if not _column_exists("workflow_runs", "workflow_definition_id"):
        op.add_column("workflow_runs", sa.Column("workflow_definition_id", sa.UUID(), nullable=True))
        op.create_foreign_key(
            "fk_workflow_runs_workflow_definition_id",
            "workflow_runs",
            "workflow_definitions",
            ["workflow_definition_id"],
            ["id"],
            ondelete="CASCADE",
        )
        op.create_index(op.f("ix_workflow_runs_workflow_definition_id"), "workflow_runs", ["workflow_definition_id"], unique=False)

    if not _column_exists("workflow_runs", "event_id"):
        op.add_column("workflow_runs", sa.Column("event_id", sa.UUID(), nullable=True))
        op.create_foreign_key(
            "fk_workflow_runs_event_id",
            "workflow_runs",
            "events",
            ["event_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index(op.f("ix_workflow_runs_event_id"), "workflow_runs", ["event_id"], unique=False)

    if not _column_exists("workflow_runs", "definition_snapshot"):
        op.add_column(
            "workflow_runs",
            sa.Column("definition_snapshot", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        )
        op.alter_column("workflow_runs", "definition_snapshot", server_default=None)

    if _column_exists("workflow_runs", "triggered_by_event_id") and _column_exists("workflow_runs", "event_id"):
        op.execute(
            "UPDATE workflow_runs "
            "SET event_id = triggered_by_event_id "
            "WHERE event_id IS NULL AND triggered_by_event_id IS NOT NULL"
        )

    if _column_exists("workflow_runs", "status"):
        if is_postgres:
            op.execute(
                """
                UPDATE workflow_runs
                SET status = CASE
                    WHEN status IN ('pending', 'queued') THEN 'queued'
                    WHEN status IN ('success', 'completed') THEN 'completed'
                    WHEN status = 'running' THEN 'running'
                    WHEN status = 'failed' THEN 'failed'
                    ELSE 'queued'
                END
                """
            )
            op.alter_column("workflow_runs", "status", server_default=None)
            op.alter_column(
                "workflow_runs",
                "status",
                existing_type=sa.String(length=20),
                type_=workflow_run_status,
                postgresql_using="status::workflow_run_status",
                nullable=False,
            )
            op.alter_column("workflow_runs", "status", server_default=sa.text("'queued'"))
        else:
            op.execute("UPDATE workflow_runs SET status = 'queued' WHERE status = 'pending'")
            op.execute("UPDATE workflow_runs SET status = 'completed' WHERE status = 'success'")

    if not _index_exists("workflow_runs", "ux_workflow_runs_event_definition"):
        op.create_index(
            "ux_workflow_runs_event_definition",
            "workflow_runs",
            ["event_id", "workflow_definition_id"],
            unique=True,
        )


def downgrade() -> None:
    """Downgrade phase-4 workflow dispatch schema changes."""
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if _table_exists("workflow_runs") and _index_exists("workflow_runs", "ux_workflow_runs_event_definition"):
        op.drop_index("ux_workflow_runs_event_definition", table_name="workflow_runs")

    if _table_exists("workflow_runs") and _column_exists("workflow_runs", "status") and is_postgres:
        op.alter_column("workflow_runs", "status", server_default=None)
        op.alter_column(
            "workflow_runs",
            "status",
            existing_type=workflow_run_status,
            type_=sa.String(length=20),
            postgresql_using="status::text",
            nullable=False,
        )
        op.execute(
            """
            UPDATE workflow_runs
            SET status = CASE
                WHEN status = 'queued' THEN 'pending'
                WHEN status = 'completed' THEN 'success'
                WHEN status = 'running' THEN 'running'
                WHEN status = 'failed' THEN 'failed'
                ELSE 'pending'
            END
            """
        )
        op.alter_column("workflow_runs", "status", server_default=sa.text("'pending'"))

    if _table_exists("workflow_runs") and _column_exists("workflow_runs", "definition_snapshot"):
        op.drop_column("workflow_runs", "definition_snapshot")

    if _table_exists("workflow_runs") and _column_exists("workflow_runs", "event_id"):
        op.drop_index(op.f("ix_workflow_runs_event_id"), table_name="workflow_runs")
        op.drop_constraint("fk_workflow_runs_event_id", "workflow_runs", type_="foreignkey")
        op.drop_column("workflow_runs", "event_id")

    if _table_exists("workflow_runs") and _column_exists("workflow_runs", "workflow_definition_id"):
        op.drop_index(op.f("ix_workflow_runs_workflow_definition_id"), table_name="workflow_runs")
        op.drop_constraint("fk_workflow_runs_workflow_definition_id", "workflow_runs", type_="foreignkey")
        op.drop_column("workflow_runs", "workflow_definition_id")

    if _table_exists("workflow_definitions"):
        op.drop_index(op.f("ix_workflow_definitions_workflow_id"), table_name="workflow_definitions")
        op.drop_index(op.f("ix_workflow_definitions_is_active"), table_name="workflow_definitions")
        op.drop_index(op.f("ix_workflow_definitions_event_type"), table_name="workflow_definitions")
        op.drop_index(op.f("ix_workflow_definitions_business_id"), table_name="workflow_definitions")
        op.drop_table("workflow_definitions")

    if is_postgres:
        workflow_run_status.drop(bind, checkfirst=True)
        op.execute("ALTER TYPE event_status RENAME VALUE 'claimed' TO 'processing'")
        op.execute("ALTER TYPE event_status RENAME VALUE 'dispatched' TO 'processed'")
