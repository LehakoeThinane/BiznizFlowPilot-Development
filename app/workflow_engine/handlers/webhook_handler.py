"""Webhook action handler."""

from __future__ import annotations

from typing import Any

import httpx  # Uses synchronous API; safe in Celery workers only.
from sqlalchemy.orm import Session

from app.core.enums import ActionFailureType
from app.workflow_engine.action_config import ActionResult, BaseActionConfig, WebhookActionConfig
from app.workflow_engine.action_handlers import ActionHandler
from app.workflow_engine.context import MissingTemplateValueError, render_template_with_context
from app.workflow_engine.template_renderer import render_template_value


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
        except (MissingTemplateValueError, ValueError) as exc:
            return ActionResult(
                status="failure",
                message=str(exc),
                failure_type=ActionFailureType.TERMINAL,
            )

        timeout_seconds = float(config.timeout_seconds or self.DEFAULT_TIMEOUT_SECONDS)

        try:
            response = httpx.request(
                method=config.method,
                url=url,
                headers=headers or None,
                json=payload,
                timeout=timeout_seconds,
            )
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
