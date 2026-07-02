"""Typed workflow action configuration and result models."""

from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from app.core.enums import ActionFailureType


class RetryPolicy(BaseModel):
    """Retry policy for a workflow action.

    Note: max_attempts=0 disables retries. Delay/backoff settings are ignored
    in that case.
    """

    model_config = ConfigDict(extra="forbid")

    max_attempts: int = Field(default=0, ge=0, le=20)
    initial_delay_seconds: int = Field(default=30, ge=1, le=3600)
    backoff_multiplier: float = Field(default=2.0, ge=1.0, le=10.0)
    max_delay_seconds: int = Field(default=900, ge=1, le=86400)
    retry_behavior: dict[ActionFailureType, bool] = Field(
        default_factory=lambda: {
            ActionFailureType.RETRYABLE: True,
            ActionFailureType.TERMINAL: False,
            ActionFailureType.SKIPPABLE: False,
        }
    )

    def should_retry(self, failure_type: ActionFailureType, attempt_count: int) -> bool:
        """Determine whether the action should be retried for this failure."""
        # No retries when max_attempts is zero, regardless of failure type map.
        if attempt_count >= self.max_attempts:
            return False
        return self.retry_behavior.get(failure_type, False)


class BaseActionConfig(BaseModel):
    """Base configuration shared by all action types."""

    model_config = ConfigDict(extra="forbid")

    action_type: str
    enabled: bool = True
    continue_on_failure: bool = False
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    timeout_seconds: int | None = Field(default=None, ge=1, le=3600)


class LogActionConfig(BaseActionConfig):
    """Log message action configuration."""

    action_type: Literal["log"]
    message: str = Field(min_length=1, max_length=2000)


class CreateTaskActionConfig(BaseActionConfig):
    """Task creation action configuration."""

    action_type: Literal["create_task"]
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    assigned_to: str | None = None


class SendEmailActionConfig(BaseActionConfig):
    """Email action configuration.

    Inherits shared execution controls from BaseActionConfig, including:
    - timeout_seconds
    - retry_policy
    - continue_on_failure
    - enabled
    """

    action_type: Literal["send_email"]
    recipient: str = Field(min_length=3, max_length=255)
    subject: str = Field(min_length=1, max_length=255)
    body_template: str = Field(min_length=1, max_length=5000)
    from_email: str | None = Field(default=None, max_length=255)
    from_name: str | None = Field(default=None, max_length=255)


class WebhookActionConfig(BaseActionConfig):
    """Webhook action configuration."""

    action_type: Literal["webhook"]
    url: str = Field(min_length=8, max_length=2000)
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"] = "POST"
    headers: dict[str, str] = Field(default_factory=dict)
    payload_template: dict[str, Any] = Field(default_factory=dict)


ActionConfig = Annotated[
    Union[
        LogActionConfig,
        CreateTaskActionConfig,
        SendEmailActionConfig,
        WebhookActionConfig,
    ],
    Field(discriminator="action_type"),
]

_action_config_adapter = TypeAdapter(ActionConfig)


class ActionResult(BaseModel):
    """Normalized action execution result contract."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["success", "failure"]
    message: str
    data: dict[str, Any] = Field(default_factory=dict)
    failure_type: ActionFailureType | None = None


def parse_action_config(payload: dict[str, Any]) -> BaseActionConfig:
    """Validate a raw action payload into a typed action config."""
    config = _action_config_adapter.validate_python(payload)
    return config
