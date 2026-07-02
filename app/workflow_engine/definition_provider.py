"""Workflow definition providers."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Iterable, List
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.enums import EventType
from app.models import WorkflowDefinition

logger = logging.getLogger(__name__)


class DefinitionProvider(ABC):
    """Source of workflow definitions for a given event."""

    @abstractmethod
    def get_definitions_for_event(
        self,
        business_id: UUID,
        event_type: EventType,
    ) -> list[WorkflowDefinition]:
        """Resolve matching definitions for a business/event pair."""


class InMemoryDefinitionProvider(DefinitionProvider):
    """In-memory definition provider used for Phase 4 and tests."""

    def __init__(self, definitions: Iterable[WorkflowDefinition] | None = None):
        self._definitions: List[WorkflowDefinition] = list(definitions or [])

    def add_definition(self, definition: WorkflowDefinition) -> None:
        """Register a definition in memory."""
        self._definitions.append(definition)

    def get_definitions_for_event(
        self,
        business_id: UUID,
        event_type: EventType,
    ) -> list[WorkflowDefinition]:
        """Return in-memory definitions matching business and event type."""
        matches: list[WorkflowDefinition] = []
        for definition in self._definitions:
            try:
                if definition.business_id != business_id:
                    continue

                definition_event_type = definition.event_type
                if isinstance(definition_event_type, str):
                    definition_event_type = EventType(definition_event_type)

                if definition_event_type == event_type:
                    matches.append(definition)
            except Exception:
                logger.warning(
                    "Skipping malformed definition during matching id=%s",
                    getattr(definition, "id", None),
                    exc_info=True,
                )
                continue

        return matches


class DatabaseDefinitionProvider(DefinitionProvider):
    """Database-backed definition provider for Phase 6.

    Pre-filters active definitions for query efficiency.
    Dispatcher still re-checks lifecycle guards before run materialization.
    """

    def __init__(self, db: Session):
        self.db = db

    def get_definitions_for_event(
        self,
        business_id: UUID,
        event_type: EventType,
    ) -> list[WorkflowDefinition]:
        """Resolve definitions matching the event directly from the database."""
        # Pre-filters is_active=True as a query optimization.
        # The dispatcher re-checks is_active as the authoritative lifecycle filter.
        definitions = (
            self.db.query(WorkflowDefinition)
            .filter(
                WorkflowDefinition.business_id == business_id,
                WorkflowDefinition.event_type == event_type,
                WorkflowDefinition.is_active.is_(True),
                WorkflowDefinition.deleted_at.is_(None),
            )
            .order_by(WorkflowDefinition.created_at.asc())
            .all()
        )
        return list(definitions)
