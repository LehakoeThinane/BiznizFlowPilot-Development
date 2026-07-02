"""Tests for WebhookHandler behavior and failure classification."""

from __future__ import annotations

import httpx
from sqlalchemy.orm import Session

from app.core.enums import ActionFailureType
from app.workflow_engine.action_config import parse_action_config
from app.workflow_engine.handlers.webhook_handler import WebhookHandler


class _FakeResponse:
    def __init__(self, status_code: int, text: str = ""):
        self.status_code = status_code
        self.text = text


def test_webhook_handler_success(test_db: Session, owner_user, sample_lead, sample_customer, monkeypatch):
    captured: dict[str, object] = {}

    def _fake_request(*, method, url, headers=None, json=None, timeout=None):
        captured["method"] = method
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return _FakeResponse(status_code=202, text="accepted")

    monkeypatch.setattr("app.workflow_engine.handlers.webhook_handler.httpx.request", _fake_request)

    handler = WebhookHandler()
    config = parse_action_config(
        {
            "action_type": "webhook",
            "url": "https://example.test/hooks/{lead.email}",
            "method": "POST",
            "timeout_seconds": 7,
            "headers": {"X-Lead-Name": "{lead.name}"},
            "payload_template": {
                "customer_email": "{customer.email}",
                "lead_status": "{lead.status}",
            },
        }
    )
    context = {
        "business_id": owner_user.business_id,
        "entity_type": "lead",
        "entity_id": str(sample_lead.id),
    }

    result = handler.execute(db=test_db, action_config=config, context=context)

    assert result.status == "success"
    assert result.failure_type is None
    assert result.data["status_code"] == 202
    assert result.data["timeout_seconds"] == 7.0
    assert captured["method"] == "POST"
    assert captured["url"] == f"https://example.test/hooks/{sample_customer.email}"
    assert captured["headers"] == {"X-Lead-Name": sample_customer.name}
    assert captured["json"] == {
        "customer_email": sample_customer.email,
        "lead_status": sample_lead.status,
    }
    assert captured["timeout"] == 7.0


def test_webhook_handler_timeout_is_retryable(test_db: Session, owner_user, sample_lead, monkeypatch):
    def _fake_request(*, method, url, headers=None, json=None, timeout=None):
        _ = method, url, headers, json, timeout
        raise httpx.ReadTimeout("read timed out")

    monkeypatch.setattr("app.workflow_engine.handlers.webhook_handler.httpx.request", _fake_request)

    handler = WebhookHandler()
    config = parse_action_config(
        {
            "action_type": "webhook",
            "url": "https://example.test/hooks",
            "method": "POST",
            "payload_template": {"lead_status": "{lead.status}"},
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


def test_webhook_handler_4xx_is_terminal(test_db: Session, owner_user, sample_lead, monkeypatch):
    monkeypatch.setattr(
        "app.workflow_engine.handlers.webhook_handler.httpx.request",
        lambda **kwargs: _FakeResponse(status_code=400, text="bad request"),
    )

    handler = WebhookHandler()
    config = parse_action_config(
        {
            "action_type": "webhook",
            "url": "https://example.test/hooks",
            "method": "POST",
            "payload_template": {"lead_status": "{lead.status}"},
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
    assert result.data["status_code"] == 400


def test_webhook_handler_5xx_is_retryable(test_db: Session, owner_user, sample_lead, monkeypatch):
    monkeypatch.setattr(
        "app.workflow_engine.handlers.webhook_handler.httpx.request",
        lambda **kwargs: _FakeResponse(status_code=503, text="unavailable"),
    )

    handler = WebhookHandler()
    config = parse_action_config(
        {
            "action_type": "webhook",
            "url": "https://example.test/hooks",
            "method": "POST",
            "payload_template": {"lead_status": "{lead.status}"},
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
    assert result.data["status_code"] == 503


def test_webhook_handler_non_retryable_5xx_is_terminal(test_db: Session, owner_user, sample_lead, monkeypatch):
    monkeypatch.setattr(
        "app.workflow_engine.handlers.webhook_handler.httpx.request",
        lambda **kwargs: _FakeResponse(status_code=501, text="not implemented"),
    )

    handler = WebhookHandler()
    config = parse_action_config(
        {
            "action_type": "webhook",
            "url": "https://example.test/hooks",
            "method": "POST",
            "payload_template": {"lead_status": "{lead.status}"},
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
    assert result.data["status_code"] == 501


def test_webhook_handler_missing_template_value_is_terminal(
    test_db: Session, owner_user, sample_lead, monkeypatch
):
    monkeypatch.setattr(
        "app.workflow_engine.handlers.webhook_handler.httpx.request",
        lambda **kwargs: _FakeResponse(status_code=200, text="ok"),
    )

    handler = WebhookHandler()
    config = parse_action_config(
        {
            "action_type": "webhook",
            "url": "https://example.test/hooks",
            "method": "POST",
            "payload_template": {"missing": "{lead.nonexistent}"},
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
    assert "Missing template value" in result.message


def test_webhook_handler_payload_depth_limit_is_terminal(test_db: Session, owner_user, sample_lead, monkeypatch):
    called = {"request_called": False}

    def _fake_request(*, method, url, headers=None, json=None, timeout=None):
        _ = method, url, headers, json, timeout
        called["request_called"] = True
        return _FakeResponse(status_code=200, text="ok")

    monkeypatch.setattr("app.workflow_engine.handlers.webhook_handler.httpx.request", _fake_request)

    deep_payload = "{lead.status}"
    for _ in range(12):
        deep_payload = [deep_payload]

    handler = WebhookHandler()
    config = parse_action_config(
        {
            "action_type": "webhook",
            "url": "https://example.test/hooks",
            "method": "POST",
            "payload_template": {"deep": deep_payload},
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
    assert "max_depth" in result.message
    assert called["request_called"] is False


def test_webhook_handler_invalid_protocol_is_terminal(test_db: Session, owner_user, sample_lead, monkeypatch):
    def _fake_request(*, method, url, headers=None, json=None, timeout=None):
        _ = method, url, headers, json, timeout
        raise httpx.UnsupportedProtocol("unsupported protocol")

    monkeypatch.setattr("app.workflow_engine.handlers.webhook_handler.httpx.request", _fake_request)

    handler = WebhookHandler()
    config = parse_action_config(
        {
            "action_type": "webhook",
            "url": "ftp://example.test/hooks",
            "method": "POST",
            "payload_template": {"lead_status": "{lead.status}"},
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
    assert "protocol" in result.message.lower()
