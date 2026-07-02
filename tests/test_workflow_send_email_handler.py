"""Tests for SendEmailHandler behavior and classification."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.enums import ActionFailureType
from app.workflow_engine.action_config import parse_action_config
from app.workflow_engine.email_provider import (
    EmailProvider,
    EmailSendResult,
    RetryableEmailProviderError,
    TerminalEmailProviderError,
)
from app.workflow_engine.handlers.send_email import SendEmailHandler


class _FakeEmailProvider(EmailProvider):
    name = "fake-email"

    def __init__(self):
        self.calls: list[dict[str, Any]] = []
        self._result: EmailSendResult | None = None
        self._error: Exception | None = None

    def queue_result(self, result: EmailSendResult) -> None:
        self._result = result
        self._error = None

    def queue_error(self, error: Exception) -> None:
        self._error = error
        self._result = None

    def send(
        self,
        *,
        recipient: str,
        subject: str,
        body: str,
        from_email: str | None = None,
        from_name: str | None = None,
        metadata: dict[str, Any] | None = None,
        timeout_seconds: int | None = None,
    ) -> EmailSendResult:
        self.calls.append(
            {
                "recipient": recipient,
                "subject": subject,
                "body": body,
                "from_email": from_email,
                "from_name": from_name,
                "metadata": metadata,
                "timeout_seconds": timeout_seconds,
            }
        )

        if self._error is not None:
            raise self._error
        if self._result is None:
            raise RuntimeError("No fake provider result queued")
        return self._result


def test_send_email_handler_success(test_db: Session, owner_user, sample_lead, sample_customer):
    provider = _FakeEmailProvider()
    provider.queue_result(
        EmailSendResult(
            provider="fake-email",
            recipient=sample_customer.email,
            subject=f"Follow up {sample_customer.name}",
            message_id="msg-123",
            metadata={"provider_region": "us-east-1"},
        )
    )
    handler = SendEmailHandler(provider=provider)
    config = parse_action_config(
        {
            "action_type": "send_email",
            "recipient": "{customer.email}",
            "subject": "Follow up {lead.name}",
            "body_template": "Hello {lead.name}, status is {lead.status}",
            "from_email": "ops@biznizflowpilot.local",
            "from_name": "Ops Bot",
            "timeout_seconds": 12,
        }
    )
    context = {
        "business_id": owner_user.business_id,
        "entity_type": "lead",
        "entity_id": str(sample_lead.id),
        "run_id": "run-123",
    }

    result = handler.execute(db=test_db, action_config=config, context=context)

    assert result.status == "success"
    assert result.failure_type is None
    assert result.data["provider"] == "fake-email"
    assert result.data["recipient"] == sample_customer.email
    assert result.data["subject"] == f"Follow up {sample_customer.name}"
    assert result.data["provider_message_id"] == "msg-123"
    assert provider.calls[0]["timeout_seconds"] == 12
    assert provider.calls[0]["from_email"] == "ops@biznizflowpilot.local"


def test_send_email_handler_missing_template_value_is_terminal(test_db: Session, owner_user, sample_lead):
    provider = _FakeEmailProvider()
    provider.queue_result(
        EmailSendResult(provider="fake-email", recipient="x@y.com", subject="s", message_id="m")
    )
    handler = SendEmailHandler(provider=provider)
    config = parse_action_config(
        {
            "action_type": "send_email",
            "recipient": "{lead.unknown}",
            "subject": "Subject",
            "body_template": "Body",
        }
    )
    context = {
        "business_id": owner_user.business_id,
        "entity_type": "lead",
        "entity_id": str(sample_lead.id),
    }

    result = handler.execute(db=test_db, action_config=config, context=context)

    assert result.status == "failure"
    assert result.failure_type == ActionFailureType.TERMINAL
    assert provider.calls == []


def test_send_email_handler_invalid_recipient_is_terminal(test_db: Session, owner_user, sample_lead):
    provider = _FakeEmailProvider()
    provider.queue_result(
        EmailSendResult(provider="fake-email", recipient="x@y.com", subject="s", message_id="m")
    )
    handler = SendEmailHandler(provider=provider)
    config = parse_action_config(
        {
            "action_type": "send_email",
            "recipient": "not-an-email",
            "subject": "Subject",
            "body_template": "Body",
        }
    )
    context = {
        "business_id": owner_user.business_id,
        "entity_type": "lead",
        "entity_id": str(sample_lead.id),
    }

    result = handler.execute(db=test_db, action_config=config, context=context)

    assert result.status == "failure"
    assert result.failure_type == ActionFailureType.TERMINAL
    assert provider.calls == []


def test_send_email_handler_empty_rendered_recipient_is_terminal(test_db: Session, owner_user, sample_lead):
    provider = _FakeEmailProvider()
    provider.queue_result(
        EmailSendResult(provider="fake-email", recipient="x@y.com", subject="s", message_id="m")
    )
    handler = SendEmailHandler(provider=provider)
    config = parse_action_config(
        {
            "action_type": "send_email",
            "recipient": "   ",
            "subject": "Subject",
            "body_template": "Body",
        }
    )
    context = {
        "business_id": owner_user.business_id,
        "entity_type": "lead",
        "entity_id": str(sample_lead.id),
    }

    result = handler.execute(db=test_db, action_config=config, context=context)

    assert result.status == "failure"
    assert result.failure_type == ActionFailureType.TERMINAL
    assert "recipient" in result.message.lower()
    assert provider.calls == []


def test_send_email_handler_empty_rendered_subject_is_terminal(test_db: Session, owner_user, sample_lead):
    provider = _FakeEmailProvider()
    provider.queue_result(
        EmailSendResult(provider="fake-email", recipient="x@y.com", subject="s", message_id="m")
    )
    handler = SendEmailHandler(provider=provider)
    config = parse_action_config(
        {
            "action_type": "send_email",
            "recipient": "user@example.com",
            "subject": "   ",
            "body_template": "Body",
        }
    )
    context = {
        "business_id": owner_user.business_id,
        "entity_type": "lead",
        "entity_id": str(sample_lead.id),
    }

    result = handler.execute(db=test_db, action_config=config, context=context)

    assert result.status == "failure"
    assert result.failure_type == ActionFailureType.TERMINAL
    assert "subject" in result.message.lower()
    assert provider.calls == []


def test_send_email_handler_retryable_provider_failure(test_db: Session, owner_user, sample_lead, sample_customer):
    provider = _FakeEmailProvider()
    provider.queue_error(
        RetryableEmailProviderError(
            "provider timeout",
            metadata={"provider_code": "TIMEOUT"},
        )
    )
    handler = SendEmailHandler(provider=provider)
    config = parse_action_config(
        {
            "action_type": "send_email",
            "recipient": "{customer.email}",
            "subject": "Follow up",
            "body_template": "Body",
        }
    )
    context = {
        "business_id": owner_user.business_id,
        "entity_type": "lead",
        "entity_id": str(sample_lead.id),
    }

    result = handler.execute(db=test_db, action_config=config, context=context)

    assert result.status == "failure"
    assert result.failure_type == ActionFailureType.RETRYABLE
    assert result.data["provider"] == "fake-email"
    assert result.data["provider_code"] == "TIMEOUT"


def test_send_email_handler_terminal_provider_failure(test_db: Session, owner_user, sample_lead):
    provider = _FakeEmailProvider()
    provider.queue_error(
        TerminalEmailProviderError(
            "invalid sender",
            metadata={"provider_code": "INVALID_SENDER"},
        )
    )
    handler = SendEmailHandler(provider=provider)
    config = parse_action_config(
        {
            "action_type": "send_email",
            "recipient": "user@example.com",
            "subject": "Follow up",
            "body_template": "Body",
        }
    )
    context = {
        "business_id": owner_user.business_id,
        "entity_type": "lead",
        "entity_id": str(sample_lead.id),
    }

    result = handler.execute(db=test_db, action_config=config, context=context)

    assert result.status == "failure"
    assert result.failure_type == ActionFailureType.TERMINAL
    assert result.data["provider"] == "fake-email"
    assert result.data["provider_code"] == "INVALID_SENDER"
