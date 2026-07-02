"""Operational metrics response schemas."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class WorkflowRunMetrics(BaseModel):
    """Aggregated run status counts."""

    total: int
    completed: int
    failed: int
    running: int


class WorkflowActionMetrics(BaseModel):
    """Aggregated action status counts."""

    total: int
    completed: int
    failed: int
    retry_scheduled: int


class WorkflowDefinitionMetrics(BaseModel):
    """Aggregated workflow-definition state counts."""

    total: int
    active: int


class MetricsResponse(BaseModel):
    """Top-level operational metrics payload."""

    business_id: UUID
    runs: WorkflowRunMetrics
    actions: WorkflowActionMetrics
    definitions: WorkflowDefinitionMetrics

