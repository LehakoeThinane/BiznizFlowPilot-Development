"""
Workflow models for automation engine.

Workflows define automation rules:
- Trigger on specific event types
- Execute configured actions in sequence
- Track execution results and status
"""

from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import relationship

from app.core.enums import ActionFailureType, EventType, WorkflowActionStatus, WorkflowRunStatus
from app.models.base import BaseModel, enum_values


class Workflow(BaseModel):
    """Workflow automation rules.

    Attributes:
        business_id: Multi-tenant identifier
        name: Human-readable workflow name
        description: Detailed explanation of workflow purpose
        trigger_event_type: Event type that triggers this workflow (e.g., 'lead_created')
        enabled: Whether workflow is active
        order: Execution order when multiple workflows match same event
    """

    __tablename__ = "workflows"

    business_id = Column(
        Uuid,
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    trigger_event_type = Column(String(100), nullable=False, index=True)
    enabled = Column(Boolean, default=True, nullable=False)
    order = Column(Integer, default=0, nullable=False)

    # Relationship to workflow actions
    actions = relationship(
        "WorkflowAction",
        foreign_keys="WorkflowAction.workflow_id",
        order_by="WorkflowAction.order",
        lazy="selectin",
    )


class WorkflowDefinition(BaseModel):
    """Workflow definition used by the dispatcher.

    This model is intentionally minimal in Phase 4 and stores enough metadata
    for matching by event type and recording immutable snapshots on run creation.
    """

    __tablename__ = "workflow_definitions"
    __table_args__ = (
        Index(
            "ix_workflow_definitions_business_event_active_created",
            "business_id",
            "event_type",
            "is_active",
            "created_at",
        ),
    )

    business_id = Column(
        Uuid,
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type = Column(
        SAEnum(EventType, name="event_type_enum", values_callable=enum_values),
        nullable=False,
        index=True,
    )
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    name = Column(String(255), nullable=False, default="Workflow Definition")
    conditions = Column(JSON, nullable=False, default=dict)
    config = Column(JSON, nullable=False, default=dict)
    deleted_at = Column(DateTime(timezone=True), nullable=True, index=True)

    # Legacy bridge while Workflow table is still used by CRUD endpoints.
    workflow_id = Column(
        Uuid,
        ForeignKey("workflows.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    def to_snapshot(self) -> dict[str, object]:
        """Serialize definition data for immutable run snapshots."""
        return {
            "id": str(self.id) if self.id else None,
            "business_id": str(self.business_id),
            "event_type": self.event_type.value if isinstance(self.event_type, EventType) else str(self.event_type),
            "is_active": bool(self.is_active),
            "name": self.name,
            "conditions": self.conditions or {},
            "config": self.config or {},
            "workflow_id": str(self.workflow_id) if self.workflow_id else None,
        }


class WorkflowAction(BaseModel):
    """Materialized action rows associated with workflow definitions and runs.

    The model supports both:
    - legacy definition-time action storage via workflow_id/order/parameters
    - run-time materialized actions via run_id/execution_order/status/result
    """

    __tablename__ = "workflow_actions"

    # Legacy bridge to definition-time workflow actions.
    workflow_id = Column(
        Uuid,
        ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    # Run-level materialization target for Phase 5.
    run_id = Column(
        Uuid,
        ForeignKey("workflow_runs.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    action_type = Column(String(100), nullable=False)
    # Legacy bridge only. Phase 5+ execution must read config_snapshot instead.
    parameters = Column(JSON, default=dict, nullable=False)
    order = Column(Integer, nullable=True)  # legacy definition order
    execution_order = Column(Integer, nullable=True, index=True)

    status = Column(
        SAEnum(WorkflowActionStatus, name="workflow_action_status", values_callable=enum_values),
        nullable=False,
        default=WorkflowActionStatus.PENDING,
        server_default=WorkflowActionStatus.PENDING.value,
        index=True,
    )
    started_at = Column(DateTime(timezone=True), nullable=True, index=True)
    finished_at = Column(DateTime(timezone=True), nullable=True, index=True)
    result = Column(JSON, default=dict, nullable=False)
    executed_at = Column(DateTime(timezone=True), nullable=True, index=True)
    error = Column(Text, nullable=True)
    failure_type = Column(
        SAEnum(ActionFailureType, name="workflow_action_failure_type", values_callable=enum_values),
        nullable=True,
        index=True,
    )

    attempt_count = Column(Integer, nullable=False, default=0, server_default="0")
    max_attempts = Column(Integer, nullable=False, default=0, server_default="0")
    next_retry_at = Column(DateTime(timezone=True), nullable=True, index=True)

    continue_on_failure = Column(Boolean, nullable=False, default=False, server_default="false")
    enabled = Column(Boolean, nullable=False, default=True, server_default="true")
    timeout_seconds = Column(Integer, nullable=True)
    # Canonical action payload for Phase 5+ execution (validated at dispatch).
    config_snapshot = Column(JSON, default=dict, nullable=False)

    @property
    def effective_execution_order(self) -> int:
        """Resolve execution order across legacy and run-time action rows."""
        if self.execution_order is not None:
            return self.execution_order
        if self.order is not None:
            return self.order
        return 0


class WorkflowRun(BaseModel):
    """Execution record created by dispatcher when an event matches definitions."""

    __tablename__ = "workflow_runs"
    __table_args__ = (
        Index(
            "ux_workflow_runs_event_definition",
            "event_id",
            "workflow_definition_id",
            unique=True,
        ),
    )

    # Legacy bridge for existing workflow CRUD APIs.
    workflow_id = Column(
        Uuid,
        ForeignKey("workflows.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    workflow_definition_id = Column(
        Uuid,
        ForeignKey("workflow_definitions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    business_id = Column(
        Uuid,
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_id = Column(
        Uuid,
        ForeignKey("events.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    actor_id = Column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status = Column(
        SAEnum(WorkflowRunStatus, name="workflow_run_status", values_callable=enum_values),
        nullable=False,
        default=WorkflowRunStatus.QUEUED,
        server_default=WorkflowRunStatus.QUEUED.value,
        index=True,
    )
    definition_snapshot = Column(JSON, nullable=False, default=dict)
    error_message = Column(Text, nullable=True)
    results = Column(JSON, default=dict, nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True, index=True)
    finished_at = Column(DateTime(timezone=True), nullable=True, index=True)

    @property
    def triggered_by_event_id(self) -> UUID | None:
        """Backward-compatible alias for legacy schema/API consumers."""
        return self.event_id

    @triggered_by_event_id.setter
    def triggered_by_event_id(self, value: UUID | None) -> None:
        self.event_id = value
