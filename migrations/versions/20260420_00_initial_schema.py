"""Initial schema for BiznizFlowPilot.

Revision ID: 20260420_00
Revises:
Create Date: 2026-04-20
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260420_00"
down_revision = None
branch_labels = None
depends_on = None


workflow_action_status = sa.Enum(
    "pending",
    "running",
    "retry_scheduled",
    "completed",
    "failed",
    "skipped",
    name="workflow_action_status",
)

workflow_action_failure_type = sa.Enum(
    "retryable",
    "terminal",
    "skippable",
    name="workflow_action_failure_type",
)


def upgrade() -> None:
    """Create the base tables used by later schema revisions."""
    bind = op.get_bind()

    op.create_table(
        "businesses",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index(op.f("ix_businesses_name"), "businesses", ["name"], unique=False)
    op.create_index(op.f("ix_businesses_email"), "businesses", ["email"], unique=False)

    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("business_id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False, server_default=sa.text("'staff'")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_business_id"), "users", ["business_id"], unique=False)
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=False)
    op.create_index(op.f("ix_users_role"), "users", ["role"], unique=False)
    op.create_index(op.f("ix_users_is_active"), "users", ["is_active"], unique=False)

    op.create_table(
        "customers",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("business_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("company", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_customers_business_id"), "customers", ["business_id"], unique=False)
    op.create_index(op.f("ix_customers_name"), "customers", ["name"], unique=False)
    op.create_index(op.f("ix_customers_email"), "customers", ["email"], unique=False)

    op.create_table(
        "leads",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("business_id", sa.UUID(), nullable=False),
        sa.Column("customer_id", sa.UUID(), nullable=True),
        sa.Column("assigned_to", sa.UUID(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default=sa.text("'new'")),
        sa.Column("source", sa.String(length=100), nullable=True),
        sa.Column("value", sa.String(length=50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assigned_to"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_leads_business_id"), "leads", ["business_id"], unique=False)
    op.create_index(op.f("ix_leads_customer_id"), "leads", ["customer_id"], unique=False)
    op.create_index(op.f("ix_leads_assigned_to"), "leads", ["assigned_to"], unique=False)
    op.create_index(op.f("ix_leads_status"), "leads", ["status"], unique=False)
    op.create_index(op.f("ix_leads_source"), "leads", ["source"], unique=False)

    op.create_table(
        "tasks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("business_id", sa.UUID(), nullable=False),
        sa.Column("lead_id", sa.UUID(), nullable=True),
        sa.Column("assigned_to", sa.UUID(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("priority", sa.String(length=50), nullable=False, server_default=sa.text("'medium'")),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assigned_to"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tasks_business_id"), "tasks", ["business_id"], unique=False)
    op.create_index(op.f("ix_tasks_lead_id"), "tasks", ["lead_id"], unique=False)
    op.create_index(op.f("ix_tasks_assigned_to"), "tasks", ["assigned_to"], unique=False)
    op.create_index(op.f("ix_tasks_status"), "tasks", ["status"], unique=False)
    op.create_index(op.f("ix_tasks_priority"), "tasks", ["priority"], unique=False)
    op.create_index(op.f("ix_tasks_due_date"), "tasks", ["due_date"], unique=False)

    op.create_table(
        "events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("business_id", sa.UUID(), nullable=False),
        sa.Column("actor_id", sa.UUID(), nullable=True),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("data", sa.JSON(), nullable=True),
        sa.Column("processed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_events_business_id"), "events", ["business_id"], unique=False)
    op.create_index(op.f("ix_events_actor_id"), "events", ["actor_id"], unique=False)
    op.create_index(op.f("ix_events_event_type"), "events", ["event_type"], unique=False)
    op.create_index(op.f("ix_events_entity_type"), "events", ["entity_type"], unique=False)
    op.create_index(op.f("ix_events_entity_id"), "events", ["entity_id"], unique=False)
    op.create_index(op.f("ix_events_processed"), "events", ["processed"], unique=False)

    op.create_table(
        "workflows",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("now()")),
        sa.Column("business_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("trigger_event_type", sa.String(length=100), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_workflows_business_id"), "workflows", ["business_id"], unique=False)
    op.create_index(op.f("ix_workflows_name"), "workflows", ["name"], unique=False)
    op.create_index(op.f("ix_workflows_trigger_event_type"), "workflows", ["trigger_event_type"], unique=False)

    op.create_table(
        "workflow_runs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("now()")),
        sa.Column("workflow_id", sa.UUID(), nullable=True),
        sa.Column("business_id", sa.UUID(), nullable=False),
        sa.Column("event_id", sa.UUID(), nullable=True),
        sa.Column("actor_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("definition_snapshot", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("results", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_workflow_runs_business_id"), "workflow_runs", ["business_id"], unique=False)
    op.create_index(op.f("ix_workflow_runs_workflow_id"), "workflow_runs", ["workflow_id"], unique=False)
    op.create_index(op.f("ix_workflow_runs_event_id"), "workflow_runs", ["event_id"], unique=False)
    op.create_index(op.f("ix_workflow_runs_actor_id"), "workflow_runs", ["actor_id"], unique=False)
    op.create_index(op.f("ix_workflow_runs_status"), "workflow_runs", ["status"], unique=False)

    op.create_table(
        "workflow_actions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("now()")),
        sa.Column("workflow_id", sa.UUID(), nullable=True),
        sa.Column("run_id", sa.UUID(), nullable=True),
        sa.Column("action_type", sa.String(length=100), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("order", sa.Integer(), nullable=True),
        sa.Column("execution_order", sa.Integer(), nullable=True),
        sa.Column("status", workflow_action_status, nullable=False, server_default=sa.text("'pending'")),
        sa.Column("result", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("failure_type", workflow_action_failure_type, nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("continue_on_failure", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("timeout_seconds", sa.Integer(), nullable=True),
        sa.Column("config_snapshot", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["workflow_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_workflow_actions_workflow_id"), "workflow_actions", ["workflow_id"], unique=False)
    op.create_index(op.f("ix_workflow_actions_run_id"), "workflow_actions", ["run_id"], unique=False)
    op.create_index(op.f("ix_workflow_actions_execution_order"), "workflow_actions", ["execution_order"], unique=False)
    op.create_index(op.f("ix_workflow_actions_status"), "workflow_actions", ["status"], unique=False)
    op.create_index(op.f("ix_workflow_actions_executed_at"), "workflow_actions", ["executed_at"], unique=False)
    op.create_index(op.f("ix_workflow_actions_failure_type"), "workflow_actions", ["failure_type"], unique=False)
    op.create_index(op.f("ix_workflow_actions_next_retry_at"), "workflow_actions", ["next_retry_at"], unique=False)


def downgrade() -> None:
    """Drop the base schema."""
    op.drop_index(op.f("ix_workflow_actions_next_retry_at"), table_name="workflow_actions")
    op.drop_index(op.f("ix_workflow_actions_failure_type"), table_name="workflow_actions")
    op.drop_index(op.f("ix_workflow_actions_executed_at"), table_name="workflow_actions")
    op.drop_index(op.f("ix_workflow_actions_status"), table_name="workflow_actions")
    op.drop_index(op.f("ix_workflow_actions_execution_order"), table_name="workflow_actions")
    op.drop_index(op.f("ix_workflow_actions_run_id"), table_name="workflow_actions")
    op.drop_index(op.f("ix_workflow_actions_workflow_id"), table_name="workflow_actions")
    op.drop_table("workflow_actions")

    op.drop_index(op.f("ix_workflow_runs_status"), table_name="workflow_runs")
    op.drop_index(op.f("ix_workflow_runs_actor_id"), table_name="workflow_runs")
    op.drop_index(op.f("ix_workflow_runs_event_id"), table_name="workflow_runs")
    op.drop_index(op.f("ix_workflow_runs_workflow_id"), table_name="workflow_runs")
    op.drop_index(op.f("ix_workflow_runs_business_id"), table_name="workflow_runs")
    op.drop_table("workflow_runs")

    op.drop_index(op.f("ix_workflows_trigger_event_type"), table_name="workflows")
    op.drop_index(op.f("ix_workflows_name"), table_name="workflows")
    op.drop_index(op.f("ix_workflows_business_id"), table_name="workflows")
    op.drop_table("workflows")

    op.drop_index(op.f("ix_events_processed"), table_name="events")
    op.drop_index(op.f("ix_events_entity_id"), table_name="events")
    op.drop_index(op.f("ix_events_entity_type"), table_name="events")
    op.drop_index(op.f("ix_events_event_type"), table_name="events")
    op.drop_index(op.f("ix_events_actor_id"), table_name="events")
    op.drop_index(op.f("ix_events_business_id"), table_name="events")
    op.drop_table("events")

    op.drop_index(op.f("ix_tasks_due_date"), table_name="tasks")
    op.drop_index(op.f("ix_tasks_priority"), table_name="tasks")
    op.drop_index(op.f("ix_tasks_status"), table_name="tasks")
    op.drop_index(op.f("ix_tasks_assigned_to"), table_name="tasks")
    op.drop_index(op.f("ix_tasks_lead_id"), table_name="tasks")
    op.drop_index(op.f("ix_tasks_business_id"), table_name="tasks")
    op.drop_table("tasks")

    op.drop_index(op.f("ix_leads_source"), table_name="leads")
    op.drop_index(op.f("ix_leads_status"), table_name="leads")
    op.drop_index(op.f("ix_leads_assigned_to"), table_name="leads")
    op.drop_index(op.f("ix_leads_customer_id"), table_name="leads")
    op.drop_index(op.f("ix_leads_business_id"), table_name="leads")
    op.drop_table("leads")

    op.drop_index(op.f("ix_customers_email"), table_name="customers")
    op.drop_index(op.f("ix_customers_name"), table_name="customers")
    op.drop_index(op.f("ix_customers_business_id"), table_name="customers")
    op.drop_table("customers")

    op.drop_index(op.f("ix_users_is_active"), table_name="users")
    op.drop_index(op.f("ix_users_role"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_index(op.f("ix_users_business_id"), table_name="users")
    op.drop_table("users")

    op.drop_index(op.f("ix_businesses_email"), table_name="businesses")
    op.drop_index(op.f("ix_businesses_name"), table_name="businesses")
    op.drop_table("businesses")

    workflow_action_failure_type.drop(bind=op.get_bind(), checkfirst=True)
    workflow_action_status.drop(bind=op.get_bind(), checkfirst=True)
