"""Tests for the daily blog autopublish decision logic - covers every
branch: human-scheduled drafts take priority, AI-generation fallback,
clean skips (empty topic queue, unconfigured AI provider), the
requires_approval hold, once-per-day idempotency, and publish-failure
recovery state."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
from sqlalchemy.orm import Session

from app.repositories.marketing_blog_post import MarketingBlogPostRepository
from app.repositories.marketing_blog_topic import MarketingBlogTopicRepository
from app.services import marketing_blog_autopublish
from app.services.marketing_blog import MarketingBlogPublishError


def _fake_github_client(*, existing_content_b64: str | None = None, new_commit_sha: str = "new-sha"):
    mock_client = MagicMock()
    get_response = MagicMock()
    if existing_content_b64 is None:
        get_response.status_code = 404
    else:
        get_response.status_code = 200
        get_response.json.return_value = {"sha": "old-sha", "content": existing_content_b64}
    mock_client.get.return_value = get_response

    put_response = MagicMock()
    put_response.raise_for_status.return_value = None
    put_response.json.return_value = {"commit": {"sha": new_commit_sha}}
    mock_client.put.return_value = put_response

    context_manager = MagicMock()
    context_manager.__enter__.return_value = mock_client
    context_manager.__exit__.return_value = False
    return context_manager


def _fake_engine(reply: str):
    class _Engine:
        @staticmethod
        def chat(messages, system_prompt):
            return type("R", (), {"reply": reply})()

    return _Engine()


@pytest.fixture(autouse=True)
def _enable_autopublish(monkeypatch):
    monkeypatch.setattr("app.services.marketing_blog_autopublish.settings.marketing_blog_autopublish_enabled", True)
    monkeypatch.setattr("app.services.marketing_blog_autopublish.settings.marketing_blog_autopublish_requires_approval", False)
    monkeypatch.setattr("app.services.marketing_blog_autopublish.settings.ai_provider", "anthropic")
    monkeypatch.setattr("app.core.config.settings.marketing_cms_github_pat", "fake-pat")


@pytest.fixture
def notify(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr("app.services.marketing_blog_autopublish.email.send_blog_autopublish_notice", mock)
    return mock


class TestDisabledAndIdempotency:
    def test_disabled_short_circuits(self, test_db: Session, notify, monkeypatch):
        monkeypatch.setattr("app.services.marketing_blog_autopublish.settings.marketing_blog_autopublish_enabled", False)
        result = marketing_blog_autopublish.run_daily_autopublish(test_db)
        assert result == {"outcome": "disabled"}
        notify.assert_not_called()

    def test_noop_if_already_published_today(self, test_db: Session, notify):
        MarketingBlogPostRepository(test_db).create(
            slug="today-post", title="Today", description="d", author="MM Nexus", content_blocks=[],
            status="published", published_at=datetime.now(timezone.utc),
        )
        result = marketing_blog_autopublish.run_daily_autopublish(test_db)
        assert result == {"outcome": "already_published_today"}
        notify.assert_not_called()

    def test_publishes_if_last_published_was_yesterday(self, test_db: Session, notify):
        MarketingBlogPostRepository(test_db).create(
            slug="yesterday-post", title="Yesterday", description="d", author="MM Nexus", content_blocks=[],
            status="published", published_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        result = marketing_blog_autopublish.run_daily_autopublish(test_db)
        assert result["outcome"] == "no_topic_available"


class TestScheduledDraftPriority:
    def test_publishes_scheduled_draft_over_generating(self, test_db: Session, notify):
        post = MarketingBlogPostRepository(test_db).create(
            slug="scheduled-post", title="Scheduled", description="d", author="MM Nexus", content_blocks=[],
            auto_publish_ready=True, pending_markdown_body="Body.",
        )
        MarketingBlogTopicRepository(test_db).create(topic="Unused topic that should be ignored")

        with patch("app.services.marketing_blog.httpx.Client", return_value=_fake_github_client()):
            result = marketing_blog_autopublish.run_daily_autopublish(test_db)

        assert result == {"outcome": "published", "post_id": str(post.id)}
        test_db.refresh(post)
        assert post.status == "published"
        assert post.auto_publish_ready is False
        assert post.pending_markdown_body is None
        assert post.github_commit_sha == "new-sha"
        notify.assert_called_once()
        assert notify.call_args[0][0] == "published"
        assert "LinkedIn: not configured" in notify.call_args[0][1]

        # The topic queue was never touched.
        assert MarketingBlogTopicRepository(test_db).get_next_unused() is not None

    def test_publish_failure_leaves_scheduled_state_for_retry(self, test_db: Session, notify):
        post = MarketingBlogPostRepository(test_db).create(
            slug="failing-post", title="Failing", description="d", author="MM Nexus", content_blocks=[],
            auto_publish_ready=True, pending_markdown_body="Body.",
        )
        with patch(
            "app.services.marketing_blog.publish", side_effect=MarketingBlogPublishError("GitHub is down")
        ):
            result = marketing_blog_autopublish.run_daily_autopublish(test_db)

        assert result == {"outcome": "failed", "post_id": str(post.id)}
        test_db.refresh(post)
        assert post.status == "draft"
        assert post.auto_publish_ready is True
        assert post.pending_markdown_body == "Body."
        assert post.published_at is None
        assert notify.call_args[0][0] == "failed"


class TestTopicFallback:
    def test_generates_and_publishes_from_oldest_unused_topic(self, test_db: Session, notify):
        MarketingBlogTopicRepository(test_db).create(topic="Why manual reconciliation is costing you")

        reply = "TITLE: Generated Title\nDESCRIPTION: Generated description.\n\nGenerated body."
        with patch("app.services.marketing_blog.get_engine", lambda: _fake_engine(reply)), patch(
            "app.services.marketing_blog.httpx.Client", return_value=_fake_github_client()
        ):
            result = marketing_blog_autopublish.run_daily_autopublish(test_db)

        assert result["outcome"] == "published"
        post = MarketingBlogPostRepository(test_db).get_by_id(UUID(result["post_id"]))
        assert post.title == "Generated Title"
        assert post.status == "published"
        assert post.github_commit_sha == "new-sha"
        assert MarketingBlogTopicRepository(test_db).get_next_unused() is None

    def test_cover_image_generated_and_included_when_configured(self, test_db: Session, notify, monkeypatch):
        monkeypatch.setattr("app.services.marketing_blog.settings.openai_api_key", "fake-key")
        MarketingBlogTopicRepository(test_db).create(topic="Why manual reconciliation is costing you")

        reply = "TITLE: Generated Title\nDESCRIPTION: Generated description.\n\nGenerated body."
        with patch("app.services.marketing_blog.get_engine", lambda: _fake_engine(reply)), patch(
            "app.services.marketing_blog.image_gen.generate_cover_image", return_value=b"fake-png"
        ), patch("app.services.marketing_blog.httpx.Client", return_value=_fake_github_client()):
            result = marketing_blog_autopublish.run_daily_autopublish(test_db)

        assert result["outcome"] == "published"
        post = MarketingBlogPostRepository(test_db).get_by_id(UUID(result["post_id"]))
        assert post.cover_image_url == "/blog/covers/generated-title.png"
        assert "cover image: generated" in notify.call_args[0][1]

    def test_cover_image_failure_does_not_block_publish(self, test_db: Session, notify):
        """openai_api_key is unset by default in tests - image generation
        should fail cleanly and the article should still publish."""
        MarketingBlogTopicRepository(test_db).create(topic="Why manual reconciliation is costing you")

        reply = "TITLE: Generated Title\nDESCRIPTION: Generated description.\n\nGenerated body."
        with patch("app.services.marketing_blog.get_engine", lambda: _fake_engine(reply)), patch(
            "app.services.marketing_blog.httpx.Client", return_value=_fake_github_client()
        ):
            result = marketing_blog_autopublish.run_daily_autopublish(test_db)

        assert result["outcome"] == "published"
        post = MarketingBlogPostRepository(test_db).get_by_id(UUID(result["post_id"]))
        assert post.cover_image_url is None
        assert "cover image: not configured" in notify.call_args[0][1]

    def test_skips_when_no_topics_and_no_scheduled_drafts(self, test_db: Session, notify):
        result = marketing_blog_autopublish.run_daily_autopublish(test_db)
        assert result == {"outcome": "no_topic_available"}
        assert notify.call_args[0][0] == "skipped"

    def test_skips_without_consuming_topic_when_ai_not_configured(self, test_db: Session, notify, monkeypatch):
        monkeypatch.setattr("app.services.marketing_blog_autopublish.settings.ai_provider", "echo")
        MarketingBlogTopicRepository(test_db).create(topic="Some topic")

        result = marketing_blog_autopublish.run_daily_autopublish(test_db)
        assert result == {"outcome": "ai_not_configured"}
        assert notify.call_args[0][0] == "skipped"
        assert MarketingBlogTopicRepository(test_db).get_next_unused() is not None

    def test_requires_approval_holds_instead_of_publishing(self, test_db: Session, notify, monkeypatch):
        monkeypatch.setattr("app.services.marketing_blog_autopublish.settings.marketing_blog_autopublish_requires_approval", True)
        MarketingBlogTopicRepository(test_db).create(topic="Needs review topic")
        reply = "TITLE: Review Me\nDESCRIPTION: Please review this.\n\nBody."

        with patch("app.services.marketing_blog.get_engine", lambda: _fake_engine(reply)):
            result = marketing_blog_autopublish.run_daily_autopublish(test_db)

        assert result["outcome"] == "needs_review"
        post = MarketingBlogPostRepository(test_db).get_by_id(UUID(result["post_id"]))
        assert post.status == "draft"
        assert post.pending_markdown_body == "Body."
        assert notify.call_args[0][0] == "needs review"
        assert MarketingBlogTopicRepository(test_db).get_next_unused() is None

    def test_publish_failure_from_topic_keeps_topic_used_and_draft_for_retry(self, test_db: Session, notify):
        MarketingBlogTopicRepository(test_db).create(topic="Failing topic")
        reply = "TITLE: Will Fail\nDESCRIPTION: This will fail to publish.\n\nBody."

        with patch("app.services.marketing_blog.get_engine", lambda: _fake_engine(reply)), patch(
            "app.services.marketing_blog.publish", side_effect=MarketingBlogPublishError("GitHub is down")
        ):
            result = marketing_blog_autopublish.run_daily_autopublish(test_db)

        assert result["outcome"] == "failed"
        post = MarketingBlogPostRepository(test_db).get_by_id(UUID(result["post_id"]))
        assert post.status == "draft"
        assert post.title == "Will Fail"
        # Topic marked used - don't regenerate a duplicate from the same topic next run.
        assert MarketingBlogTopicRepository(test_db).get_next_unused() is None


class _FixedSessionContext:
    def __init__(self, session: Session):
        self._session = session

    def __enter__(self) -> Session:
        return self._session

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class TestDailyBlogAutopublishTask:
    def test_task_delegates_to_service_and_returns_result(self, test_db: Session, notify, monkeypatch):
        from app.workers import marketing_blog_autopublish as autopublish_task

        monkeypatch.setattr(autopublish_task, "SessionLocal", lambda: _FixedSessionContext(test_db))
        result = autopublish_task.daily_blog_autopublish_task.run()
        assert result == {"outcome": "no_topic_available"}
        assert notify.call_args[0][0] == "skipped"
