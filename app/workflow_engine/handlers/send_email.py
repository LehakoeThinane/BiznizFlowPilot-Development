"""Send Email action handler."""

from __future__ import annotations

from email.utils import parseaddr
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.core.enums import ActionFailureType
from app.workflow_engine.action_config import ActionResult, BaseActionConfig, SendEmailActionConfig
from app.workflow_engine.action_handlers import ActionHandler
from app.workflow_engine.context import MissingTemplateValueError
from app.workflow_engine.email_provider import (
    EmailProvider,
    EmailProviderError,
    RetryableEmailProviderError,
    TerminalEmailProviderError,
    build_default_email_provider,
)
from app.workflow_engine.template_renderer import render_template_string

logger = logging.getLogger(__name__)


class SendEmailHandler(ActionHandler):
    """Action handler that sends templated notification emails."""

    action_type = "send_email"

    def __init__(self, provider: EmailProvider | None = None):
        self.provider = provider or build_default_email_provider()

    def execute(
        self,
        *,
        db: Session,
        action_config: BaseActionConfig,
        context: dict[str, Any],
    ) -> ActionResult:
        """Render templates, validate recipient, call provider, classify failures."""
        # Defensive validation at handler boundary. Action payloads are already
        # validated at definition/dispatch time, but this guards against any
        # malformed direct invocation paths.
        config = SendEmailActionConfig.model_validate(action_config.model_dump())

        try:
            recipient = render_template_string(db, context, config.recipient).strip()
            subject = render_template_string(db, context, config.subject).strip()
            body = render_template_string(db, context, config.body_template)
            from_email = (
                render_template_string(db, context, config.from_email).strip()
                if config.from_email
                else None
            )
            from_name = (
                render_template_string(db, context, config.from_name).strip()
                if config.from_name
                else None
            )
        except MissingTemplateValueError as exc:
            return ActionResult(
                status="failure",
                message=str(exc),
                failure_type=ActionFailureType.TERMINAL,
            )

        if not recipient:
            return ActionResult(
                status="failure",
                message="Rendered recipient is empty",
                failure_type=ActionFailureType.TERMINAL,
            )
        if not subject:
            return ActionResult(
                status="failure",
                message="Rendered subject is empty",
                failure_type=ActionFailureType.TERMINAL,
            )
        if not self._is_valid_email(recipient):
            return ActionResult(
                status="failure",
                message=f"Invalid recipient email address: {recipient}",
                failure_type=ActionFailureType.TERMINAL,
            )

        try:
            send_result = self.provider.send(
                recipient=recipient,
                subject=subject,
                body=body,
                from_email=from_email,
                from_name=from_name,
                metadata={
                    "run_id": context.get("run_id"),
                    "event_id": context.get("event_id"),
                    "workflow_definition_id": context.get("workflow_definition_id"),
                },
                timeout_seconds=config.timeout_seconds,
            )
        except RetryableEmailProviderError as exc:
            return ActionResult(
                status="failure",
                message=str(exc),
                failure_type=ActionFailureType.RETRYABLE,
                data={"provider": self.provider.name, **exc.metadata},
            )
        except TerminalEmailProviderError as exc:
            return ActionResult(
                status="failure",
                message=str(exc),
                failure_type=ActionFailureType.TERMINAL,
                data={"provider": self.provider.name, **exc.metadata},
            )
        except EmailProviderError as exc:
            return ActionResult(
                status="failure",
                message=str(exc),
                failure_type=ActionFailureType.TERMINAL,
                data={"provider": self.provider.name, **exc.metadata},
            )
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.exception("Unexpected SendEmailHandler execution error")
            return ActionResult(
                status="failure",
                message=f"Unexpected email provider error: {exc}",
                failure_type=ActionFailureType.TERMINAL,
                data={"provider": self.provider.name},
            )

        return ActionResult(
            status="success",
            message=f"Email accepted for delivery to {recipient}",
            data={
                "provider": send_result.provider,
                "recipient": recipient,
                "subject": subject,
                "provider_message_id": send_result.message_id,
                "provider_metadata": send_result.metadata,
            },
            failure_type=None,
        )

    @staticmethod
    def _is_valid_email(value: str) -> bool:
        """Basic recipient validation before provider call."""
        _name, addr = parseaddr(value)
        if not addr or "@" not in addr:
            return False
        local, _, domain = addr.rpartition("@")
        if not local or not domain or "." not in domain:
            return False
        return True
