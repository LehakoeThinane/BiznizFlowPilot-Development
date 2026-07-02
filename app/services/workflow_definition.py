"""Workflow definition service with write-time validation and soft delete."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.enums import EventType
from app.core.permissions import PRIVILEGED_ROLES, require_role
from app.models import WorkflowDefinition
from app.repositories.workflow import WorkflowDefinitionRepository
from app.schemas.auth import CurrentUser
from app.schemas.workflow import WorkflowDefinitionCreate, WorkflowDefinitionUpdate
from app.workflow_engine.definition_validation import validate_and_normalize_definition_config


class WorkflowDefinitionService:
    """Business logic for workflow definition CRUD."""

    def __init__(self, db: Session):
        self.db = db
        self.repo = WorkflowDefinitionRepository(db)

    def create(
        self,
        *,
        business_id: UUID,
        current_user: CurrentUser,
        data: WorkflowDefinitionCreate,
    ) -> WorkflowDefinition:
        """Create definition from already-validated schema payload."""
        require_role(current_user, PRIVILEGED_ROLES, "create workflow definitions")
        definition = self.repo.create_definition(
            db=self.db,
            business_id=business_id,
            event_type=data.event_type,
            is_active=data.is_active,
            name=data.name,
            conditions=data.conditions,
            config=data.config,
            workflow_id=data.workflow_id,
        )
        self.db.commit()
        self.db.refresh(definition)
        return definition

    def list(
        self,
        *,
        business_id: UUID,
        event_type: EventType | None = None,
        is_active: bool | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[WorkflowDefinition], int]:
        """List non-deleted definitions with optional filters."""
        items = self.repo.list(
            db=self.db,
            business_id=business_id,
            event_type=event_type,
            is_active=is_active,
            skip=skip,
            limit=limit,
        )
        total = self.repo.count(
            db=self.db,
            business_id=business_id,
            event_type=event_type,
            is_active=is_active,
        )
        return items, total

    def get(self, *, business_id: UUID, definition_id: UUID) -> WorkflowDefinition | None:
        """Get one non-deleted definition by ID."""
        return self.repo.get(
            db=self.db,
            business_id=business_id,
            definition_id=definition_id,
        )

    def update(
        self,
        *,
        business_id: UUID,
        current_user: CurrentUser,
        definition_id: UUID,
        data: WorkflowDefinitionUpdate,
    ) -> WorkflowDefinition | None:
        """Patch definition fields.

        If config is patched, action payloads are re-validated.
        """
        require_role(current_user, PRIVILEGED_ROLES, "update workflow definitions")

        definition = self.repo.get(
            db=self.db,
            business_id=business_id,
            definition_id=definition_id,
        )
        if definition is None:
            return None

        updates = data.model_dump(exclude_unset=True)

        # Activation safety: re-validate existing config when re-enabling without
        # an explicit config patch, so broken definitions cannot be reactivated.
        # Re-validates the currently-stored config for structural integrity only.
        # It does not protect against configs that reference removed action types
        # or deprecated field names introduced by future schema evolution.
        if updates.get("is_active") is True and "config" not in updates:
            validate_and_normalize_definition_config(definition.config or {})

        definition = self.repo.update_definition(
            db=self.db,
            business_id=business_id,
            definition_id=definition_id,
            **updates,
        )
        if definition is None:
            return None

        self.db.commit()
        self.db.refresh(definition)
        return definition

    def soft_delete(
        self,
        *,
        business_id: UUID,
        current_user: CurrentUser,
        definition_id: UUID,
    ) -> bool:
        """Soft delete definition by setting deleted_at and disabling it."""
        require_role(current_user, PRIVILEGED_ROLES, "delete workflow definitions")

        definition = self.repo.soft_delete(
            db=self.db,
            business_id=business_id,
            definition_id=definition_id,
        )
        if definition is None:
            return False

        self.db.commit()
        return True
