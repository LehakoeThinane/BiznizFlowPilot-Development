"""
Workflow request and response schemas.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.enums import EventType, WorkflowRunStatus
from app.workflow_engine.definition_validation import validate_and_normalize_definition_config


class WorkflowActionCreate(BaseModel):
    """Create workflow action request."""

    action_type: str = Field(..., min_length=1, max_length=100)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    order: int


class WorkflowActionResponse(WorkflowActionCreate):
    """Workflow action response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workflow_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime


class WorkflowCreate(BaseModel):
    """Create workflow request."""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    trigger_event_type: str = Field(..., min_length=1, max_length=100)
    enabled: bool = True
    order: int = 0
    actions: List[WorkflowActionCreate] = Field(default_factory=list)

    @field_validator("actions")
    @classmethod
    def validate_actions(cls, v: List[WorkflowActionCreate]) -> List[WorkflowActionCreate]:
        """Ensure actions are ordered correctly."""
        if v:
            sorted_actions = sorted(v, key=lambda a: a.order)
            for i, action in enumerate(sorted_actions):
                if action.order != i:
                    raise ValueError("Actions must have sequential order starting from 0")
        return v


class WorkflowUpdate(BaseModel):
    """Update workflow request."""

    name: Optional[str] = None
    description: Optional[str] = None
    trigger_event_type: Optional[str] = None
    enabled: Optional[bool] = None
    order: Optional[int] = None


class WorkflowResponse(BaseModel):
    """Workflow response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    name: str
    description: Optional[str]
    trigger_event_type: str
    enabled: bool
    order: int
    actions: List[WorkflowActionResponse]
    created_at: datetime
    updated_at: datetime


class WorkflowDefinitionCreate(BaseModel):
    """Create workflow definition request."""

    event_type: EventType
    is_active: bool = True
    name: str = Field(default="Workflow Definition", min_length=1, max_length=255)
    conditions: Dict[str, Any] = Field(default_factory=dict)
    config: Dict[str, Any] = Field(default_factory=dict)
    workflow_id: Optional[UUID] = None

    @field_validator("config")
    @classmethod
    def validate_config(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        return validate_and_normalize_definition_config(value)


class WorkflowDefinitionUpdate(BaseModel):
    """Patch workflow definition request."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    is_active: Optional[bool] = None
    config: Optional[Dict[str, Any]] = None

    @field_validator("config")
    @classmethod
    def validate_config(cls, value: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if value is None:
            return None
        return validate_and_normalize_definition_config(value)


class WorkflowDefinitionResponse(BaseModel):
    """Workflow definition response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    event_type: EventType
    is_active: bool
    name: str
    conditions: Dict[str, Any]
    config: Dict[str, Any]
    workflow_id: Optional[UUID] = None
    deleted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class WorkflowDefinitionListResponse(BaseModel):
    """List response for workflow definitions."""

    items: List[WorkflowDefinitionResponse]
    total: int
    skip: int
    limit: int


class WorkflowListResponse(BaseModel):
    """Workflow list response."""

    total: int
    workflows: List[WorkflowResponse]


class WorkflowRunResponse(BaseModel):
    """Workflow run response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workflow_id: Optional[UUID]
    workflow_definition_id: Optional[UUID]
    business_id: UUID
    event_id: Optional[UUID]
    triggered_by_event_id: Optional[UUID]
    actor_id: Optional[UUID]
    status: WorkflowRunStatus
    definition_snapshot: Dict[str, Any]
    error_message: Optional[str]
    results: Dict[str, Any]
    created_at: datetime
    updated_at: datetime


class WorkflowRunListResponse(BaseModel):
    """Workflow run list response."""

    total: int
    runs: List[WorkflowRunResponse]
