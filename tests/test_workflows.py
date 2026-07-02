"""
Tests for workflow automation engine.
"""

import pytest
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.enums import WorkflowRunStatus
from app.models import Workflow, WorkflowAction, WorkflowRun
from app.schemas.workflow import WorkflowCreate, WorkflowActionCreate, WorkflowUpdate
from app.services.workflow import WorkflowService


class TestWorkflowCreate:
    """Test workflow creation."""

    def test_owner_can_create_workflow(self, db: Session, owner: dict, business_id: UUID):
        """Owner can create workflows."""
        service = WorkflowService()

        workflow_data = WorkflowCreate(
            name="New Lead Workflow",
            description="Auto-create task when lead is created",
            trigger_event_type="lead_created",
            enabled=True,
            order=1,
            actions=[
                WorkflowActionCreate(
                    action_type="create_task",
                    parameters={"title": "Follow up with {entity_id}", "assigned_to": "manager"},
                    order=0,
                ),
                WorkflowActionCreate(
                    action_type="log",
                    parameters={"message": "New lead workflow triggered"},
                    order=1,
                ),
            ],
        )

        workflow = service.create_workflow(
            db=db,
            business_id=business_id,
            current_user=owner["user"],
            data=workflow_data,
        )

        assert workflow.id is not None
        assert workflow.business_id == business_id
        assert workflow.name == "New Lead Workflow"
        assert workflow.trigger_event_type == "lead_created"
        assert workflow.enabled is True

    def test_manager_can_create_workflow(self, db: Session, manager: dict, business_id: UUID):
        """Manager can create workflows."""
        service = WorkflowService()

        workflow_data = WorkflowCreate(
            name="Manager Workflow",
            trigger_event_type="task_assigned",
            actions=[
                WorkflowActionCreate(
                    action_type="send_email",
                    parameters={"recipient": "{actor_id}", "subject": "Task assigned"},
                    order=0,
                ),
            ],
        )

        workflow = service.create_workflow(
            db=db,
            business_id=business_id,
            current_user=manager["user"],
            data=workflow_data,
        )

        assert workflow.id is not None
        assert workflow.name == "Manager Workflow"

    def test_staff_cannot_create_workflow(self, db: Session, staff: dict, business_id: UUID):
        """Staff cannot create workflows."""
        service = WorkflowService()

        workflow_data = WorkflowCreate(
            name="Staff Workflow",
            trigger_event_type="lead_created",
        )

        with pytest.raises(PermissionError):
            service.create_workflow(
                db=db,
                business_id=business_id,
                current_user=staff["user"],
                data=workflow_data,
            )

    def test_workflow_with_multiple_actions(self, db: Session, owner: dict, business_id: UUID):
        """Workflow can have multiple ordered actions."""
        service = WorkflowService()

        workflow_data = WorkflowCreate(
            name="Complex Workflow",
            trigger_event_type="lead_created",
            actions=[
                WorkflowActionCreate(action_type="log", parameters={"message": "Step 1"}, order=0),
                WorkflowActionCreate(action_type="create_task", parameters={"title": "Follow up"}, order=1),
                WorkflowActionCreate(action_type="send_email", parameters={"recipient": "admin@example.com"}, order=2),
            ],
        )

        workflow = service.create_workflow(
            db=db,
            business_id=business_id,
            current_user=owner["user"],
            data=workflow_data,
        )

        actions = service.action_repository.get_by_workflow(db, workflow.id)
        assert len(actions) == 3
        assert [a.order for a in actions] == [0, 1, 2]


class TestWorkflowRead:
    """Test workflow retrieval."""

    def test_get_workflow_by_id(self, db: Session, owner: dict, business_id: UUID):
        """Can retrieve workflow by ID."""
        service = WorkflowService()

        # Create workflow
        workflow_data = WorkflowCreate(
            name="Test Workflow",
            trigger_event_type="lead_created",
        )
        created = service.create_workflow(db, business_id, owner["user"], workflow_data)

        # Retrieve it
        retrieved = service.get_workflow(
            db=db,
            business_id=business_id,
            current_user=owner["user"],
            workflow_id=created.id,
        )

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.name == "Test Workflow"

    def test_list_all_workflows(self, db: Session, owner: dict, business_id: UUID):
        """Can list all workflows for business."""
        service = WorkflowService()

        # Create multiple workflows
        for i in range(3):
            workflow_data = WorkflowCreate(
                name=f"Workflow {i}",
                trigger_event_type="lead_created",
            )
            service.create_workflow(db, business_id, owner["user"], workflow_data)

        workflows = service.list_workflows(db, business_id, owner["user"])

        assert len(workflows) == 3
        assert all(w.business_id == business_id for w in workflows)

    def test_get_nonexistent_workflow_returns_none(self, db: Session, owner: dict, business_id: UUID):
        """Getting nonexistent workflow returns None."""
        service = WorkflowService()
        fake_id = UUID("00000000-0000-0000-0000-000000000000")

        result = service.get_workflow(
            db=db,
            business_id=business_id,
            current_user=owner["user"],
            workflow_id=fake_id,
        )

        assert result is None


class TestWorkflowUpdate:
    """Test workflow updating."""

    def test_owner_can_update_workflow(self, db: Session, owner: dict, business_id: UUID):
        """Owner can update workflow."""
        service = WorkflowService()

        # Create
        workflow_data = WorkflowCreate(
            name="Original Name",
            trigger_event_type="lead_created",
        )
        workflow = service.create_workflow(db, business_id, owner["user"], workflow_data)

        # Update
        update_data = WorkflowUpdate(name="Updated Name", enabled=False)
        updated = service.update_workflow(
            db=db,
            business_id=business_id,
            current_user=owner["user"],
            workflow_id=workflow.id,
            data=update_data,
        )

        assert updated.name == "Updated Name"
        assert updated.enabled is False

    def test_staff_cannot_update_workflow(self, db: Session, owner: dict, staff: dict, business_id: UUID):
        """Staff cannot update workflow."""
        service = WorkflowService()

        workflow_data = WorkflowCreate(name="Test", trigger_event_type="lead_created")
        workflow = service.create_workflow(db, business_id, owner["user"], workflow_data)

        update_data = WorkflowUpdate(name="New Name")

        with pytest.raises(PermissionError):
            service.update_workflow(
                db=db,
                business_id=business_id,
                current_user=staff["user"],
                workflow_id=workflow.id,
                data=update_data,
            )

    def test_partial_update(self, db: Session, owner: dict, business_id: UUID):
        """Can update only specific fields."""
        service = WorkflowService()

        workflow_data = WorkflowCreate(
            name="Original", description="Original desc", trigger_event_type="lead_created"
        )
        workflow = service.create_workflow(db, business_id, owner["user"], workflow_data)

        # Update only name
        update_data = WorkflowUpdate(name="New Name")
        updated = service.update_workflow(
            db=db,
            business_id=business_id,
            current_user=owner["user"],
            workflow_id=workflow.id,
            data=update_data,
        )

        assert updated.name == "New Name"
        assert updated.description == "Original desc"  # Unchanged


class TestWorkflowDelete:
    """Test workflow deletion."""

    def test_owner_can_delete_workflow(self, db: Session, owner: dict, business_id: UUID):
        """Owner can delete workflow."""
        service = WorkflowService()

        workflow_data = WorkflowCreate(name="Delete Me", trigger_event_type="lead_created")
        workflow = service.create_workflow(db, business_id, owner["user"], workflow_data)

        success = service.delete_workflow(
            db=db,
            business_id=business_id,
            current_user=owner["user"],
            workflow_id=workflow.id,
        )

        assert success is True

        # Verify deleted
        retrieved = service.get_workflow(db, business_id, owner["user"], workflow.id)
        assert retrieved is None

    def test_staff_cannot_delete_workflow(self, db: Session, owner: dict, staff: dict, business_id: UUID):
        """Staff cannot delete workflow."""
        service = WorkflowService()

        workflow_data = WorkflowCreate(name="Test", trigger_event_type="lead_created")
        workflow = service.create_workflow(db, business_id, owner["user"], workflow_data)

        with pytest.raises(PermissionError):
            service.delete_workflow(
                db=db,
                business_id=business_id,
                current_user=staff["user"],
                workflow_id=workflow.id,
            )

    def test_delete_nonexistent_returns_false(self, db: Session, owner: dict, business_id: UUID):
        """Deleting nonexistent workflow returns False."""
        service = WorkflowService()
        fake_id = UUID("00000000-0000-0000-0000-000000000000")

        success = service.delete_workflow(
            db=db,
            business_id=business_id,
            current_user=owner["user"],
            workflow_id=fake_id,
        )

        assert success is False


class TestWorkflowToggle:
    """Test enable/disable workflows."""

    def test_toggle_workflow_enabled(self, db: Session, owner: dict, business_id: UUID):
        """Can toggle workflow enabled status."""
        service = WorkflowService()

        workflow_data = WorkflowCreate(name="Test", trigger_event_type="lead_created", enabled=True)
        workflow = service.create_workflow(db, business_id, owner["user"], workflow_data)

        # Disable
        updated = service.toggle_workflow(
            db=db,
            business_id=business_id,
            current_user=owner["user"],
            workflow_id=workflow.id,
            enabled=False,
        )

        assert updated.enabled is False

        # Re-enable
        updated = service.toggle_workflow(
            db=db,
            business_id=business_id,
            current_user=owner["user"],
            workflow_id=workflow.id,
            enabled=True,
        )

        assert updated.enabled is True

    def test_get_enabled_workflows(self, db: Session, owner: dict, business_id: UUID):
        """Can query only enabled workflows."""
        service = WorkflowService()

        # Create 3 workflows: 2 enabled, 1 disabled
        for i in range(2):
            workflow_data = WorkflowCreate(name=f"Enabled {i}", trigger_event_type="lead_created", enabled=True)
            service.create_workflow(db, business_id, owner["user"], workflow_data)

        workflow_data = WorkflowCreate(name="Disabled", trigger_event_type="lead_created", enabled=False)
        service.create_workflow(db, business_id, owner["user"], workflow_data)

        enabled = service.repository.get_all_enabled(db, business_id)
        assert len(enabled) == 2
        assert all(w.enabled for w in enabled)


class TestWorkflowExecution:
    """Test workflow execution logic."""

    def test_execute_workflow_with_single_action(self, db: Session, owner: dict, business_id: UUID):
        """Can execute workflow with single action."""
        service = WorkflowService()

        workflow_data = WorkflowCreate(
            name="Log Workflow",
            trigger_event_type="lead_created",
            actions=[
                WorkflowActionCreate(action_type="log", parameters={"message": "Test log"}, order=0),
            ],
        )
        workflow = service.create_workflow(db, business_id, owner["user"], workflow_data)

        result = service.execute_workflow(
            db=db,
            business_id=business_id,
            workflow_id=workflow.id,
            event_data={"entity_id": "lead-123", "event_type": "lead_created"},
        )

        assert result["success"] is True
        assert len(result["actions"]) == 1
        assert result["actions"]["0"]["success"] is True

    def test_execute_workflow_with_multiple_actions(self, db: Session, owner: dict, business_id: UUID):
        """Workflows execute all actions in order."""
        service = WorkflowService()

        workflow_data = WorkflowCreate(
            name="Multi-action Workflow",
            trigger_event_type="lead_created",
            actions=[
                WorkflowActionCreate(action_type="log", parameters={"message": "Step 1"}, order=0),
                WorkflowActionCreate(action_type="create_task", parameters={"title": "Follow up"}, order=1),
                WorkflowActionCreate(action_type="send_email", parameters={"recipient": "test@test.com"}, order=2),
            ],
        )
        workflow = service.create_workflow(db, business_id, owner["user"], workflow_data)

        result = service.execute_workflow(
            db=db,
            business_id=business_id,
            workflow_id=workflow.id,
            event_data={},
        )

        assert result["success"] is True
        assert len(result["actions"]) == 3

    def test_execute_workflow_with_unknown_action_type(self, db: Session, owner: dict, business_id: UUID):
        """Unknown action types fail gracefully."""
        service = WorkflowService()

        workflow_data = WorkflowCreate(
            name="Invalid Action Workflow",
            trigger_event_type="lead_created",
            actions=[
                WorkflowActionCreate(action_type="unknown_action", parameters={}, order=0),
            ],
        )
        workflow = service.create_workflow(db, business_id, owner["user"], workflow_data)

        result = service.execute_workflow(
            db=db,
            business_id=business_id,
            workflow_id=workflow.id,
            event_data={},
        )

        assert result["actions"]["0"]["success"] is False
        assert "Unknown action type" in result["actions"]["0"]["error"]

    def test_get_workflows_for_event_type(self, db: Session, owner: dict, business_id: UUID):
        """Can query workflows by trigger event type."""
        service = WorkflowService()

        # Create workflows for different event types
        for event_type in ["lead_created", "task_assigned", "lead_created"]:
            workflow_data = WorkflowCreate(
                name=f"Workflow for {event_type}",
                trigger_event_type=event_type,
            )
            service.create_workflow(db, business_id, owner["user"], workflow_data)

        lead_workflows = service.get_workflows_for_event(db, business_id, "lead_created")

        assert len(lead_workflows) == 2
        assert all(w.trigger_event_type == "lead_created" for w in lead_workflows)


class TestWorkflowRuns:
    """Test workflow run tracking."""

    def test_create_run(self, db: Session, owner: dict, business_id: UUID):
        """Can create workflow run record."""
        service = WorkflowService()

        workflow_data = WorkflowCreate(name="Test Workflow", trigger_event_type="lead_created")
        workflow = service.create_workflow(db, business_id, owner["user"], workflow_data)

        run = service.create_run(
            db=db,
            business_id=business_id,
            workflow_id=workflow.id,
        )

        assert run.id is not None
        assert run.workflow_id == workflow.id
        assert run.business_id == business_id
        assert run.status == WorkflowRunStatus.QUEUED

    def test_update_run_status(self, db: Session, owner: dict, business_id: UUID):
        """Can update run status."""
        service = WorkflowService()

        workflow_data = WorkflowCreate(name="Test", trigger_event_type="lead_created")
        workflow = service.create_workflow(db, business_id, owner["user"], workflow_data)

        run = service.create_run(db=db, business_id=business_id, workflow_id=workflow.id)

        updated = service.update_run_status(
            db=db,
            business_id=business_id,
            run_id=run.id,
            status=WorkflowRunStatus.COMPLETED,
        )

        assert updated.status == WorkflowRunStatus.COMPLETED

    def test_add_run_result(self, db: Session, owner: dict, business_id: UUID):
        """Can add action results to run."""
        service = WorkflowService()

        workflow_data = WorkflowCreate(name="Test", trigger_event_type="lead_created")
        workflow = service.create_workflow(db, business_id, owner["user"], workflow_data)

        run = service.create_run(db=db, business_id=business_id, workflow_id=workflow.id)

        service.add_run_result(
            db=db,
            business_id=business_id,
            run_id=run.id,
            action_index=0,
            result={"success": True, "message": "Action completed"},
        )

        updated = service.get_run(db, business_id, run.id)
        assert updated.results["actions"]["0"]["success"] is True

    def test_get_pending_runs(self, db: Session, owner: dict, business_id: UUID):
        """Can query pending runs for execution."""
        service = WorkflowService()

        workflow_data = WorkflowCreate(name="Test", trigger_event_type="lead_created")
        workflow = service.create_workflow(db, business_id, owner["user"], workflow_data)

        # Create 3 runs: 2 queued, 1 completed
        for i in range(2):
            service.create_run(db=db, business_id=business_id, workflow_id=workflow.id)

        run = service.create_run(db=db, business_id=business_id, workflow_id=workflow.id)
        service.update_run_status(db, business_id, run.id, WorkflowRunStatus.COMPLETED)

        pending = service.get_pending_runs(db, business_id)
        assert len(pending) == 2
        assert all(r.status == WorkflowRunStatus.QUEUED for r in pending)


class TestWorkflowMultiTenancy:
    """Test multi-tenancy enforcement."""

    def test_workflow_isolated_by_business(self, db: Session, owner: dict, business_id: UUID, other_business_id: UUID):
        """Workflows are isolated by business_id."""
        service = WorkflowService()

        # Create workflow in business 1
        workflow_data = WorkflowCreate(name="Business 1 Workflow", trigger_event_type="lead_created")
        workflow = service.create_workflow(db, business_id, owner["user"], workflow_data)

        # Cannot retrieve in business 2
        retrieved = service.get_workflow(
            db=db,
            business_id=other_business_id,
            current_user=owner["user"],
            workflow_id=workflow.id,
        )

        assert retrieved is None

    def test_list_workflows_filtered_by_business(
        self, db: Session, owner: dict, other_owner: dict, business_id: UUID, other_business_id: UUID
    ):
        """List workflows only shows business's workflows."""
        service = WorkflowService()

        # Business 1: 2 workflows
        for i in range(2):
            workflow_data = WorkflowCreate(name=f"Business 1 Workflow {i}", trigger_event_type="lead_created")
            service.create_workflow(db, business_id, owner["user"], workflow_data)

        # Business 2: 1 workflow
        workflow_data = WorkflowCreate(name="Business 2 Workflow", trigger_event_type="lead_created")
        service.create_workflow(db, other_business_id, other_owner["user"], workflow_data)

        # Business 1 sees 2
        biz1_workflows = service.list_workflows(db, business_id, owner["user"])
        assert len(biz1_workflows) == 2

        # Business 2 sees 1
        biz2_workflows = service.list_workflows(db, other_business_id, other_owner["user"])
        assert len(biz2_workflows) == 1
