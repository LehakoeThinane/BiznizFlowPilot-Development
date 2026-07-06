"""Tests for WebhookHandler behavior and failure classification."""

from __future__ import annotations

import json

import httpx
from sqlalchemy.orm import Session

from app.core.enums import ActionFailureType
from app.workflow_engine.action_config import parse_action_config
from app.workflow_engine.handlers.webhook_handler import WebhookHandler


class _FakeResponse:
    def __init__(self, status_code: int, text: str = ""):
        self.status_code = status_code
        self.text = text


def _capture_send(captured: dict[str, object], response: "_FakeResponse | Exception"):
    """Build a fake httpx.Client.send that records the outgoing request and
    returns/raises the given response/exception - the seam these tests mock
    is Client.send rather than the removed httpx.request() call, since the
    handler now builds requests through a Client to attach the sni_hostname
    extension used for SSRF-safe IP pinning (see webhook_handler.py)."""

    def _fake_send(self, request, **kwargs):
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        body = request.read()
        captured["json"] = json.loads(body) if body else None
        captured["timeout"] = request.extensions.get("timeout")
        if isinstance(response, Exception):
            raise response
        return response

    return _fake_send


def test_webhook_handler_success(test_db: Session, owner_user, sample_lead, sample_customer, monkeypatch):
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        "app.workflow_engine.handlers.webhook_handler.resolve_pinned_request",
        lambda url: (url, {"Host": "example.test"}, {"sni_hostname": "example.test"}),
    )
    monkeypatch.setattr(httpx.Client, "send", _capture_send(captured, _FakeResponse(status_code=202, text="accepted")))

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
    assert captured["headers"]["x-lead-name"] == sample_customer.name
    assert captured["headers"]["host"] == "example.test"
    assert captured["json"] == {
        "customer_email": sample_customer.email,
        "lead_status": sample_lead.status,
    }


def test_webhook_handler_timeout_is_retryable(test_db: Session, owner_user, sample_lead, monkeypatch):
    monkeypatch.setattr(
        "app.workflow_engine.handlers.webhook_handler.resolve_pinned_request",
        lambda url: (url, {"Host": "example.test"}, {"sni_hostname": "example.test"}),
    )
    monkeypatch.setattr(httpx.Client, "send", _capture_send({}, httpx.ReadTimeout("read timed out")))

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
        "app.workflow_engine.handlers.webhook_handler.resolve_pinned_request",
        lambda url: (url, {"Host": "example.test"}, {"sni_hostname": "example.test"}),
    )
    monkeypatch.setattr(httpx.Client, "send", _capture_send({}, _FakeResponse(status_code=400, text="bad request")))

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
        "app.workflow_engine.handlers.webhook_handler.resolve_pinned_request",
        lambda url: (url, {"Host": "example.test"}, {"sni_hostname": "example.test"}),
    )
    monkeypatch.setattr(httpx.Client, "send", _capture_send({}, _FakeResponse(status_code=503, text="unavailable")))

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
        "app.workflow_engine.handlers.webhook_handler.resolve_pinned_request",
        lambda url: (url, {"Host": "example.test"}, {"sni_hostname": "example.test"}),
    )
    monkeypatch.setattr(httpx.Client, "send", _capture_send({}, _FakeResponse(status_code=501, text="not implemented")))

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
        "app.workflow_engine.handlers.webhook_handler.resolve_pinned_request",
        lambda url: (url, {"Host": "example.test"}, {"sni_hostname": "example.test"}),
    )
    monkeypatch.setattr(httpx.Client, "send", _capture_send({}, _FakeResponse(status_code=200, text="ok")))

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

    def _fake_send(self, request, **kwargs):
        called["request_called"] = True
        return _FakeResponse(status_code=200, text="ok")

    monkeypatch.setattr(
        "app.workflow_engine.handlers.webhook_handler.resolve_pinned_request",
        lambda url: (url, {"Host": "example.test"}, {"sni_hostname": "example.test"}),
    )
    monkeypatch.setattr(httpx.Client, "send", _fake_send)

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
    # No resolve_pinned_request/Client.send mock needed - ftp:// is rejected
    # by resolve_pinned_request's own scheme check before any network call.
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


def test_webhook_handler_sends_idempotency_key_from_action_id(
    test_db: Session, owner_user, sample_lead, monkeypatch
):
    """A stable Idempotency-Key lets a receiver that honors the convention
    recognize a retried delivery instead of double-processing it."""
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        "app.workflow_engine.handlers.webhook_handler.resolve_pinned_request",
        lambda url: (url, {"Host": "example.test"}, {"sni_hostname": "example.test"}),
    )
    monkeypatch.setattr(httpx.Client, "send", _capture_send(captured, _FakeResponse(status_code=200, text="ok")))

    handler = WebhookHandler()
    config = parse_action_config(
        {
            "action_type": "webhook",
            "url": "https://example.test/hooks",
            "method": "POST",
            "payload_template": {"lead_status": "{lead.status}"},
        }
    )
    action_id = "3f9c1a5e-8b2d-4a11-9f0e-6d2c8a1b7e44"
    context = {
        "business_id": owner_user.business_id,
        "entity_type": "lead",
        "entity_id": str(sample_lead.id),
        "action_id": action_id,
    }

    result = handler.execute(db=test_db, action_config=config, context=context)

    assert result.status == "success"
    assert captured["headers"]["idempotency-key"] == action_id


def test_webhook_handler_no_action_id_omits_idempotency_key(
    test_db: Session, owner_user, sample_lead, monkeypatch
):
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        "app.workflow_engine.handlers.webhook_handler.resolve_pinned_request",
        lambda url: (url, {"Host": "example.test"}, {"sni_hostname": "example.test"}),
    )
    monkeypatch.setattr(httpx.Client, "send", _capture_send(captured, _FakeResponse(status_code=200, text="ok")))

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

    handler.execute(db=test_db, action_config=config, context=context)

    assert "idempotency-key" not in captured["headers"]
