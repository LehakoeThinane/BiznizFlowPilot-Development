"""Tests for the webhook SSRF guard (resolve_pinned_request) - both the
resolution/validation logic in isolation and its end-to-end wiring into
WebhookHandler.execute(), proving a disallowed destination is rejected
before any network call is attempted."""

from __future__ import annotations

import socket

import httpx
import pytest
from sqlalchemy.orm import Session

from app.core.enums import ActionFailureType
from app.workflow_engine.action_config import parse_action_config
from app.workflow_engine.handlers.webhook_handler import (
    WebhookHandler,
    WebhookSSRFError,
    resolve_pinned_request,
)


def _fake_getaddrinfo(ip: str, family=socket.AF_INET):
    def _inner(host, port, proto=None):
        return [(family, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (ip, port))]

    return _inner


class TestResolvePinnedRequestRejections:
    @pytest.mark.parametrize(
        "ip,label",
        [
            ("10.0.0.5", "private (RFC1918)"),
            ("172.16.0.5", "private (RFC1918)"),
            ("192.168.1.5", "private (RFC1918)"),
            ("127.0.0.1", "loopback"),
            ("169.254.169.254", "link-local / cloud metadata"),
            ("0.0.0.0", "unspecified"),
            ("224.0.0.1", "multicast"),
        ],
    )
    def test_rejects_disallowed_ip(self, monkeypatch, ip, label):
        monkeypatch.setattr(
            "app.workflow_engine.handlers.webhook_handler.socket.getaddrinfo", _fake_getaddrinfo(ip)
        )
        with pytest.raises(WebhookSSRFError, match=ip):
            resolve_pinned_request("https://attacker-controlled.test/hook")

    def test_rejects_unresolvable_host(self, monkeypatch):
        def _raise(host, port, proto=None):
            raise socket.gaierror("name not known")

        monkeypatch.setattr("app.workflow_engine.handlers.webhook_handler.socket.getaddrinfo", _raise)
        with pytest.raises(WebhookSSRFError, match="Could not resolve"):
            resolve_pinned_request("https://nonexistent.test/hook")

    @pytest.mark.parametrize("scheme", ["ftp", "file", "gopher"])
    def test_rejects_unsupported_scheme(self, scheme):
        with pytest.raises(WebhookSSRFError, match="protocol"):
            resolve_pinned_request(f"{scheme}://example.test/hook")

    def test_rejects_url_with_no_host(self):
        with pytest.raises(WebhookSSRFError, match="no host"):
            resolve_pinned_request("https:///hook")


class TestResolvePinnedRequestSuccess:
    def test_pins_to_resolved_public_ip_and_sets_sni_for_https(self, monkeypatch):
        monkeypatch.setattr(
            "app.workflow_engine.handlers.webhook_handler.socket.getaddrinfo",
            _fake_getaddrinfo("93.184.216.34"),
        )

        pinned_url, headers, extensions = resolve_pinned_request("https://real-vendor.test/hooks/abc?x=1")

        assert pinned_url == "https://93.184.216.34:443/hooks/abc?x=1"
        assert headers == {"Host": "real-vendor.test"}
        assert extensions == {"sni_hostname": "real-vendor.test"}

    def test_plain_http_has_no_sni_extension(self, monkeypatch):
        monkeypatch.setattr(
            "app.workflow_engine.handlers.webhook_handler.socket.getaddrinfo",
            _fake_getaddrinfo("93.184.216.34"),
        )

        pinned_url, headers, extensions = resolve_pinned_request("http://real-vendor.test/hooks")

        assert pinned_url == "http://93.184.216.34:80/hooks"
        assert extensions == {}

    def test_respects_explicit_port(self, monkeypatch):
        monkeypatch.setattr(
            "app.workflow_engine.handlers.webhook_handler.socket.getaddrinfo",
            _fake_getaddrinfo("93.184.216.34"),
        )

        pinned_url, _headers, _extensions = resolve_pinned_request("https://real-vendor.test:8443/hooks")

        assert pinned_url == "https://93.184.216.34:8443/hooks"

    def test_pins_ipv6_with_brackets(self, monkeypatch):
        monkeypatch.setattr(
            "app.workflow_engine.handlers.webhook_handler.socket.getaddrinfo",
            _fake_getaddrinfo("2606:2800:220:1:248:1893:25c8:1946", family=socket.AF_INET6),
        )

        pinned_url, _headers, _extensions = resolve_pinned_request("https://real-vendor.test/hooks")

        assert pinned_url == "https://[2606:2800:220:1:248:1893:25c8:1946]:443/hooks"


class TestWebhookHandlerEndToEndSSRFRejection:
    def test_private_target_is_rejected_without_any_network_call(
        self, test_db: Session, owner_user, sample_lead, monkeypatch
    ):
        monkeypatch.setattr(
            "app.workflow_engine.handlers.webhook_handler.socket.getaddrinfo",
            _fake_getaddrinfo("169.254.169.254"),
        )

        network_called = {"value": False}

        def _fail_if_called(self, request, **kwargs):
            network_called["value"] = True
            raise AssertionError("network layer must not be reached for a disallowed destination")

        monkeypatch.setattr(httpx.Client, "send", _fail_if_called)

        handler = WebhookHandler()
        config = parse_action_config(
            {
                "action_type": "webhook",
                "url": "https://attacker-controlled.test/steal-metadata",
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

        assert network_called["value"] is False
        assert result.status == "failure"
        assert result.failure_type == ActionFailureType.TERMINAL
        assert "disallowed" in result.message.lower()
