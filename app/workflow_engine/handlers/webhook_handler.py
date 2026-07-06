"""Webhook action handler."""

from __future__ import annotations

import ipaddress
import socket
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx  # Uses synchronous API; safe in Celery workers only.
from sqlalchemy.orm import Session

from app.core.enums import ActionFailureType
from app.workflow_engine.action_config import ActionResult, BaseActionConfig, WebhookActionConfig
from app.workflow_engine.action_handlers import ActionHandler
from app.workflow_engine.context import MissingTemplateValueError, render_template_with_context
from app.workflow_engine.template_renderer import render_template_value


class WebhookSSRFError(ValueError):
    """Raised when a tenant-configured webhook URL resolves to a destination
    that must not be reachable from a backend worker (private network,
    loopback, link-local/metadata, multicast, or an unsupported scheme)."""


def _is_disallowed_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def resolve_pinned_request(url: str) -> tuple[str, dict[str, str], dict[str, Any]]:
    """Resolve a webhook URL's host, reject disallowed destinations, and
    return (pinned_url, extra_headers, extensions) that connect directly to
    the validated IP instead of letting httpx re-resolve the hostname at
    connect time.

    Validating the hostname and then letting the HTTP client re-resolve it
    itself is a DNS-rebinding gap: the name can resolve to a public IP for
    this check and to a private/metadata IP a moment later when the actual
    connection is made. Pinning to the IP we just validated closes that
    window. The original Host header and TLS SNI are preserved via the
    sni_hostname extension so name-based virtual hosting and certificate
    validation still work correctly against the real target.
    """
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise WebhookSSRFError(f"Unsupported webhook URL protocol: {parts.scheme!r}")

    hostname = parts.hostname
    if not hostname:
        raise WebhookSSRFError("Webhook URL has no host")

    port = parts.port or (443 if parts.scheme == "https" else 80)

    try:
        addr_infos = socket.getaddrinfo(hostname, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise WebhookSSRFError(f"Could not resolve webhook host {hostname!r}: {exc}") from exc

    resolved: list[tuple[int, str]] = []
    for family, _type, _proto, _canonname, sockaddr in addr_infos:
        ip = ipaddress.ip_address(sockaddr[0])
        if _is_disallowed_ip(ip):
            raise WebhookSSRFError(
                f"Webhook host {hostname!r} resolves to a disallowed address ({ip})"
            )
        resolved.append((family, sockaddr[0]))

    family, ip_literal = resolved[0]
    netloc_host = f"[{ip_literal}]" if family == socket.AF_INET6 else ip_literal
    pinned_url = urlunsplit(
        (parts.scheme, f"{netloc_host}:{port}", parts.path or "/", parts.query, parts.fragment)
    )

    extra_headers = {"Host": hostname}
    extensions: dict[str, Any] = {"sni_hostname": hostname} if parts.scheme == "https" else {}
    return pinned_url, extra_headers, extensions


class WebhookHandler(ActionHandler):
    """Action handler that performs outbound HTTP webhook requests."""

    action_type = "webhook"
    DEFAULT_TIMEOUT_SECONDS = 10
    MAX_RESPONSE_BODY_CHARS = 1000

    def execute(
        self,
        *,
        db: Session,
        action_config: BaseActionConfig,
        context: dict[str, Any],
    ) -> ActionResult:
        """Execute webhook side effect with handler-scoped timeout enforcement."""
        config = WebhookActionConfig.model_validate(action_config.model_dump())

        try:
            url = render_template_with_context(db, context, config.url)
            headers = {
                key: render_template_with_context(db, context, value)
                for key, value in config.headers.items()
            }
            payload = render_template_value(db, context, config.payload_template)
            pinned_url, pin_headers, extensions = resolve_pinned_request(url)
        except (MissingTemplateValueError, ValueError) as exc:
            return ActionResult(
                status="failure",
                message=str(exc),
                failure_type=ActionFailureType.TERMINAL,
            )

        # A stable per-action key lets a receiver that honors this de-facto
        # convention (Stripe/GitHub-style Idempotency-Key) recognize a
        # retried delivery - after a timeout where the first attempt actually
        # reached the endpoint - as the same request rather than a new one.
        # We don't control the receiving server, so this is best-effort, not
        # a guarantee; it's the correct mechanism available for an outbound
        # call we don't own both ends of.
        action_id = context.get("action_id")
        idempotency_headers = {"Idempotency-Key": action_id} if action_id else {}
        headers = {**headers, **pin_headers, **idempotency_headers}
        timeout_seconds = float(config.timeout_seconds or self.DEFAULT_TIMEOUT_SECONDS)

        try:
            with httpx.Client() as client:
                request = client.build_request(
                    method=config.method,
                    url=pinned_url,
                    headers=headers,
                    json=payload,
                    timeout=timeout_seconds,
                    extensions=extensions,
                )
                response = client.send(request)
        except httpx.InvalidURL as exc:
            return ActionResult(
                status="failure",
                message=f"Invalid webhook URL: {exc}",
                failure_type=ActionFailureType.TERMINAL,
            )
        except httpx.UnsupportedProtocol as exc:
            return ActionResult(
                status="failure",
                message=f"Invalid webhook URL protocol: {exc}",
                failure_type=ActionFailureType.TERMINAL,
            )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            return ActionResult(
                status="failure",
                message=f"Webhook request failed with retryable transport error: {exc}",
                failure_type=ActionFailureType.RETRYABLE,
            )
        except httpx.RequestError as exc:
            return ActionResult(
                status="failure",
                message=f"Webhook request failed: {exc}",
                failure_type=ActionFailureType.RETRYABLE,
            )

        status_code = int(response.status_code)
        response_body = response.text[: self.MAX_RESPONSE_BODY_CHARS]
        result_data = {
            "url": url,
            "method": config.method,
            "status_code": status_code,
            "response_body": response_body,
            "timeout_seconds": timeout_seconds,
        }
        if 200 <= status_code < 300:
            return ActionResult(
                status="success",
                message=f"Webhook delivered with status {status_code}",
                data=result_data,
            )

        retryable_codes = {408, 429, 500, 502, 503, 504}
        failure_type = (
            ActionFailureType.RETRYABLE
            if status_code in retryable_codes
            else ActionFailureType.TERMINAL
        )
        return ActionResult(
            status="failure",
            message=f"Webhook returned status {status_code}",
            data=result_data,
            failure_type=failure_type,
        )
