"""Workflow service for automation engine."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.enums import WorkflowRunStatus
from app.models import Workflow, WorkflowAction, WorkflowRun
from app.repositories.workflow import WorkflowActionRepository, WorkflowRepository, WorkflowRunRepository
from app.schemas.auth import CurrentUser
from app.schemas.workflow import WorkflowCreate, WorkflowUpdate


class WorkflowService:
    """Service for workflow automation."""

    def __init__(self, db: Session | None = None):
        self.db = db
        self.repository: WorkflowRepository | None = None
        self.action_repository: WorkflowActionRepository | None = None
        self.run_repository: WorkflowRunRepository | None = None

        if db is not None:
            self._bind_repositories(db)

    def _bind_repositories(self, db: Session | None) -> Session:
        active_db = db or self.db
        if active_db is None:
            raise ValueError("Database session is required")

        if self.db is not active_db or self.repository is None:
            self.db = active_db
            self.repository = WorkflowRepository(active_db)
            self.action_repository = WorkflowActionRepository(active_db)
            self.run_repository = WorkflowRunRepository(active_db)

        return active_db

    @staticmethod
    def _check_role(current_user: CurrentUser, allowed_roles: List[str]) -> None:
        if current_user.role.lower() not in {role.lower() for role in allowed_roles}:
            raise PermissionError(f"User role '{current_user.role}' not in allowed roles: {allowed_roles}")

    @staticmethod
    def _normalize_run_status(status: WorkflowRunStatus | str) -> WorkflowRunStatus:
        """Support legacy status inputs while standardizing lifecycle values."""
        if isinstance(status, WorkflowRunStatus):
            return status

        normalized = status.lower().strip()
        legacy_map = {
            "pending": WorkflowRunStatus.QUEUED,
            "success": WorkflowRunStatus.COMPLETED,
        }
        if normalized in legacy_map:
            return legacy_map[normalized]
        return WorkflowRunStatus(normalized)

    def create_workflow(
        self,
        db: Session,
        business_id: UUID,
        current_user: CurrentUser,
        data: WorkflowCreate,
    ) -> Workflow:
        session = self._bind_repositories(db)
        self._check_role(current_user, ["owner", "manager"])

        workflow = Workflow(
            business_id=business_id,
            name=data.name,
            description=data.description,
            trigger_event_type=data.trigger_event_type,
            enabled=data.enabled,
            order=data.order,
        )
        session.add(workflow)
        session.flush()

        for action_data in data.actions:
            action = WorkflowAction(
                workflow_id=workflow.id,
                action_type=action_data.action_type,
                parameters=action_data.parameters,
                order=action_data.order,
            )
            session.add(action)

        session.commit()
        session.refresh(workflow)
        return workflow

    def get_workflow(
        self,
        db: Session,
        business_id: UUID,
        current_user: CurrentUser,
        workflow_id: UUID,
    ) -> Optional[Workflow]:
        self._bind_repositories(db)
        return self.repository.get(db, business_id, workflow_id)  # type: ignore[union-attr]

    def list_workflows(
        self,
        db: Session,
        business_id: UUID,
        current_user: CurrentUser,
    ) -> List[Workflow]:
        self._bind_repositories(db)
        return self.repository.list(db, business_id)  # type: ignore[union-attr]

    def update_workflow(
        self,
        db: Session,
        business_id: UUID,
        current_user: CurrentUser,
        workflow_id: UUID,
        data: WorkflowUpdate,
    ) -> Optional[Workflow]:
        session = self._bind_repositories(db)
        self._check_role(current_user, ["owner", "manager"])

        workflow = self.repository.get(db, business_id, workflow_id)  # type: ignore[union-attr]
        if workflow is None:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(workflow, field, value)

        session.commit()
        session.refresh(workflow)
        return workflow

    def delete_workflow(
        self,
        db: Session,
        business_id: UUID,
        current_user: CurrentUser,
        workflow_id: UUID,
    ) -> bool:
        session = self._bind_repositories(db)
        self._check_role(current_user, ["owner", "manager"])

        workflow = self.repository.get(db, business_id, workflow_id)  # type: ignore[union-attr]
        if workflow is None:
            return False

        session.delete(workflow)
        session.commit()
        return True

    def toggle_workflow(
        self,
        db: Session,
        business_id: UUID,
        current_user: CurrentUser,
        workflow_id: UUID,
        enabled: bool,
    ) -> Optional[Workflow]:
        self._bind_repositories(db)
        self._check_role(current_user, ["owner", "manager"])
        return self.repository.toggle_enabled(db, business_id, workflow_id, enabled)  # type: ignore[union-attr]

    def get_workflows_for_event(self, db: Session, business_id: UUID, event_type: str) -> List[Workflow]:
        self._bind_repositories(db)
        return self.repository.get_by_event_type(db, business_id, event_type)  # type: ignore[union-attr]

    def create_run(
        self,
        db: Session,
        business_id: UUID,
        workflow_id: UUID,
        workflow_definition_id: Optional[UUID] = None,
        event_id: Optional[UUID] = None,
        triggered_by_event_id: Optional[UUID] = None,
        actor_id: Optional[UUID] = None,
        definition_snapshot: Optional[dict[str, Any]] = None,
    ) -> WorkflowRun:
        session = self._bind_repositories(db)
        run = WorkflowRun(
            workflow_id=workflow_id,
            workflow_definition_id=workflow_definition_id,
            business_id=business_id,
            event_id=event_id or triggered_by_event_id,
            actor_id=actor_id,
            status=WorkflowRunStatus.QUEUED,
            definition_snapshot=definition_snapshot or {},
            results={},
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        return run

    def update_run_status(
        self,
        db: Session,
        business_id: UUID,
        run_id: UUID,
        status: WorkflowRunStatus | str,
        error_message: Optional[str] = None,
    ) -> Optional[WorkflowRun]:
        session = self._bind_repositories(db)
        run = self.run_repository.get(db, business_id, run_id)  # type: ignore[union-attr]
        if run is None:
            return None

        run.status = self._normalize_run_status(status)
        if error_message:
            run.error_message = error_message

        session.commit()
        session.refresh(run)
        return run

    def add_run_result(
        self,
        db: Session,
        business_id: UUID,
        run_id: UUID,
        action_index: int,
        result: Dict[str, Any],
    ) -> Optional[WorkflowRun]:
        session = self._bind_repositories(db)
        run = self.run_repository.get(db, business_id, run_id)  # type: ignore[union-attr]
        if run is None:
            return None

        if not run.results:
            run.results = {}
        if "actions" not in run.results or not isinstance(run.results["actions"], dict):
            run.results["actions"] = {}

        run.results["actions"][str(action_index)] = result
        session.commit()
        session.refresh(run)
        return run

    def get_run(self, db: Session, business_id: UUID, run_id: UUID) -> Optional[WorkflowRun]:
        self._bind_repositories(db)
        return self.run_repository.get(db, business_id, run_id)  # type: ignore[union-attr]

    def list_runs(self, db: Session, business_id: UUID, current_user: CurrentUser) -> List[WorkflowRun]:
        self._bind_repositories(db)
        return self.run_repository.list(db, business_id)  # type: ignore[union-attr]

    def get_pending_runs(self, db: Session, business_id: UUID) -> List[WorkflowRun]:
        self._bind_repositories(db)
        return self.run_repository.get_pending(db, business_id)  # type: ignore[union-attr]

    def execute_workflow(self, db: Session, business_id: UUID, workflow_id: UUID, event_data: Dict[str, Any]) -> Dict[str, Any]:
        self._bind_repositories(db)
        workflow = self.repository.get(db, business_id, workflow_id)  # type: ignore[union-attr]
        if workflow is None:
            return {"success": False, "error": "Workflow not found"}

        actions = self.action_repository.get_by_workflow(workflow_id)  # type: ignore[union-attr]
        if not actions:
            return {"success": True, "actions_count": 0, "actions": {}}

        results: Dict[str, Any] = {"actions": {}}
        for index, action in enumerate(actions):
            try:
                action_result = self._execute_action(action, event_data)
                results["actions"][str(index)] = action_result
            except Exception as exc:
                results["actions"][str(index)] = {"success": False, "error": str(exc)}

        results["success"] = all(action.get("success", False) for action in results["actions"].values())
        return results

    def _execute_action(self, action: WorkflowAction, event_data: Dict[str, Any]) -> Dict[str, Any]:
        action_type = action.action_type
        parameters = action.parameters or {}

        if action_type == "log":
            return {
                "success": True,
                "action": action_type,
                "message": parameters.get("message", "Workflow executed"),
            }
        if action_type == "send_email":
            return {
                "success": True,
                "action": action_type,
                "recipient": parameters.get("recipient"),
                "subject": parameters.get("subject"),
            }
        if action_type == "create_task":
            return {
                "success": True,
                "action": action_type,
                "title": parameters.get("title"),
                "assigned_to": parameters.get("assigned_to"),
            }
        if action_type == "webhook":
            return {
                "success": True,
                "action": action_type,
                "url": parameters.get("url"),
            }

        return {
            "success": False,
            "action": action_type,
            "error": f"Unknown action type: {action_type}",
        }
