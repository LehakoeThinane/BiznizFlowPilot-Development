"""Tests for app/services/lead_reply_watcher.py - detects a lead-gen lead
replying to its automated follow-up and escalates to staff."""

from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.core.crypto import encrypt_secret
from app.integrations.imap_client import ImapConnectionError, MessageSummary
from app.models.customer import Customer
from app.models.lead import Lead
from app.models.notification import Notification
from app.models.user_email import UserEmailAccount
from app.repositories.user_email import UserEmailAccountRepository
from app.schemas.auth import CurrentUser
from app.services.lead_reply_watcher import LeadReplyWatcherService
from app.workers.lead_reply_watcher import check_lead_replies_task


def _connected_account(test_db: Session, owner_user: CurrentUser) -> UserEmailAccount:
    account = UserEmailAccount(
        id=uuid4(),
        business_id=owner_user.business_id,
        user_id=owner_user.user_id,
        imap_host="mail.example.com",
        imap_port=993,
        imap_username="owner@example.com",
        imap_password_encrypted=encrypt_secret("real-password"),
    )
    test_db.add(account)
    test_db.commit()
    return account


def _lead_gen_lead(test_db: Session, business_id, email: str, source: str, status: str = "new") -> Lead:
    customer = Customer(id=uuid4(), business_id=business_id, name="Acme Plumbing", email=email)
    test_db.add(customer)
    test_db.commit()
    lead = Lead(id=uuid4(), business_id=business_id, customer_id=customer.id, source=source, status=status)
    test_db.add(lead)
    test_db.commit()
    return lead


def _msg(from_address: str) -> MessageSummary:
    return MessageSummary(uid="1", from_address=from_address, subject="Re: hi", date=None, is_read=False)


class TestUserEmailAccountListAllConnected:
    def test_lists_accounts_with_full_imap_config(self, test_db: Session, owner_user: CurrentUser):
        _connected_account(test_db, owner_user)
        incomplete = UserEmailAccount(
            id=uuid4(), business_id=owner_user.business_id, user_id=uuid4(), imap_host="mail.example.com",
        )
        test_db.add(incomplete)
        test_db.commit()

        accounts = UserEmailAccountRepository(test_db).list_all_connected()

        assert len(accounts) == 1


class TestLeadReplyWatcher:
    def test_reply_from_lead_gen_lead_escalates_and_notifies(self, test_db: Session, owner_user: CurrentUser):
        account = _connected_account(test_db, owner_user)
        lead = _lead_gen_lead(
            test_db, owner_user.business_id, "prospect@example.com", "google_places_no_website"
        )

        with patch(
            "app.services.lead_reply_watcher.imap_client.list_messages",
            return_value=[_msg("Acme Plumbing <prospect@example.com>")],
        ):
            result = LeadReplyWatcherService(test_db).check_all_accounts()

        test_db.commit()  # check_all_accounts doesn't commit - the real caller (Celery task) does

        assert result["leads_escalated"] == 1
        assert lead.status == "contacted"
        notif = test_db.query(Notification).filter(Notification.related_id == lead.id).first()
        assert notif is not None
        assert notif.user_id == owner_user.user_id  # falls back to mailbox owner, no assignee set

    def test_reply_from_manually_created_lead_not_escalated(self, test_db: Session, owner_user: CurrentUser):
        _connected_account(test_db, owner_user)
        lead = _lead_gen_lead(test_db, owner_user.business_id, "prospect@example.com", "referral")

        with patch(
            "app.services.lead_reply_watcher.imap_client.list_messages",
            return_value=[_msg("prospect@example.com")],
        ):
            result = LeadReplyWatcherService(test_db).check_all_accounts()

        assert result["leads_escalated"] == 0
        assert lead.status == "new"

    def test_already_contacted_lead_not_re_escalated(self, test_db: Session, owner_user: CurrentUser):
        _connected_account(test_db, owner_user)
        _lead_gen_lead(
            test_db, owner_user.business_id, "prospect@example.com", "google_places_no_website",
            status="contacted",
        )

        with patch(
            "app.services.lead_reply_watcher.imap_client.list_messages",
            return_value=[_msg("prospect@example.com")],
        ):
            result = LeadReplyWatcherService(test_db).check_all_accounts()

        assert result["leads_escalated"] == 0

    def test_unknown_sender_is_a_no_op(self, test_db: Session, owner_user: CurrentUser):
        _connected_account(test_db, owner_user)

        with patch(
            "app.services.lead_reply_watcher.imap_client.list_messages",
            return_value=[_msg("stranger@example.com")],
        ):
            result = LeadReplyWatcherService(test_db).check_all_accounts()

        assert result["leads_escalated"] == 0
        assert result["accounts_checked"] == 1

    def test_one_account_imap_failure_does_not_block_others(
        self, test_db: Session, owner_user: CurrentUser, other_user: CurrentUser
    ):
        _connected_account(test_db, owner_user)
        _connected_account(test_db, other_user)
        _lead_gen_lead(test_db, other_user.business_id, "prospect@example.com", "google_places_no_website")

        calls = {"n": 0}

        def _fake_list_messages(host, port, username, password, limit=25):
            calls["n"] += 1
            if calls["n"] == 1:
                raise ImapConnectionError("boom")
            return [_msg("prospect@example.com")]

        with patch("app.services.lead_reply_watcher.imap_client.list_messages", side_effect=_fake_list_messages):
            result = LeadReplyWatcherService(test_db).check_all_accounts()

        assert result["accounts_failed"] == 1
        assert result["accounts_checked"] == 1
        assert result["leads_escalated"] == 1


class TestCheckLeadRepliesTaskMasterSwitch:
    def test_task_skips_when_disabled(self, test_db: Session, owner_user: CurrentUser):
        _connected_account(test_db, owner_user)

        with patch("app.workers.lead_reply_watcher.settings.lead_reply_watch_enabled", False), \
             patch("app.workers.lead_reply_watcher.SessionLocal", return_value=test_db), \
             patch("app.services.lead_reply_watcher.imap_client.list_messages") as mock_list:
            result = check_lead_replies_task()

        mock_list.assert_not_called()
        assert result["status"] == "skipped"

    def test_task_runs_when_enabled(self, test_db: Session, owner_user: CurrentUser):
        _connected_account(test_db, owner_user)

        with patch("app.workers.lead_reply_watcher.settings.lead_reply_watch_enabled", True), \
             patch("app.workers.lead_reply_watcher.SessionLocal", return_value=test_db), \
             patch("app.services.lead_reply_watcher.imap_client.list_messages", return_value=[]):
            result = check_lead_replies_task()

        assert result["status"] == "ok"
        assert result["accounts_checked"] == 1
