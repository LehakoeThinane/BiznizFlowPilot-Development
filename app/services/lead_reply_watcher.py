"""Watches connected mailboxes for a reply from a lead-gen-sourced lead
and escalates to staff to take over personally (see app/services/
lead_followup.py for the automated first-touch email this watches for a
response to).

Idempotency has no separate "already seen this message" tracking - a
lead only ever escalates once because escalating flips its status out of
_UNESCALATED_STATUSES, so re-polling the same still-recent message again
next run is a harmless no-op (the lead is simply no longer eligible).
"""

from __future__ import annotations

import logging
from email.utils import parseaddr
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.crypto import decrypt_secret
from app.integrations import imap_client
from app.integrations.imap_client import ImapError
from app.repositories.customer import CustomerRepository
from app.repositories.lead import LeadRepository
from app.repositories.user_email import UserEmailAccountRepository
from app.utils.notify import notify_user

logger = logging.getLogger(__name__)

_UNESCALATED_STATUSES = ("new", "qualified")
_POLL_LIMIT = 25


class LeadReplyWatcherService:
    def __init__(self, db: Session):
        self.db = db

    def check_all_accounts(self) -> dict[str, int]:
        accounts = UserEmailAccountRepository(self.db).list_all_connected()

        accounts_checked = 0
        accounts_failed = 0
        leads_escalated = 0

        for account in accounts:
            try:
                password = decrypt_secret(account.imap_password_encrypted)
                messages = imap_client.list_messages(
                    account.imap_host, account.imap_port, account.imap_username, password, limit=_POLL_LIMIT,
                )
                accounts_checked += 1
            except ImapError:
                logger.exception("lead_reply_watcher failed to poll account %s", account.id)
                accounts_failed += 1
                continue
            except Exception:
                logger.exception("lead_reply_watcher unexpected error polling account %s", account.id)
                accounts_failed += 1
                continue

            senders = {parseaddr(m.from_address)[1].lower() for m in messages if m.from_address}
            senders.discard("")

            for sender_email in senders:
                leads_escalated += self._escalate_leads_from(
                    account.business_id, account.user_id, sender_email
                )

        return {
            "accounts_checked": accounts_checked,
            "accounts_failed": accounts_failed,
            "leads_escalated": leads_escalated,
        }

    def _escalate_leads_from(self, business_id: UUID, mailbox_user_id: UUID, sender_email: str) -> int:
        customer = CustomerRepository(self.db).get_by_email(business_id, sender_email)
        if customer is None:
            return 0

        leads = LeadRepository(self.db).get_by_customer(business_id, customer.id)
        escalated = 0
        for lead in leads:
            if not (lead.source or "").startswith("google_places_"):
                continue
            if lead.status not in _UNESCALATED_STATUSES:
                continue

            lead.status = "contacted"
            notify_user(
                self.db,
                business_id,
                lead.assigned_to or mailbox_user_id,
                "system",
                f"{customer.name} replied",
                f"{customer.name} replied to your outreach email - take over personally.",
                action_url="/leads",
                related_type="lead",
                related_id=lead.id,
            )
            escalated += 1

        return escalated
