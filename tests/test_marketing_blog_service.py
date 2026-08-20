"""Unit tests for the marketing blog service's full-post generation and
slug helpers - the pieces the daily autopublish task needs beyond the
existing generate_content()/publish() covered by test_marketing_cms_blog.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.repositories.marketing_blog_post import MarketingBlogPostRepository
from app.services import marketing_blog


def _fake_github_client(new_commit_sha: str = "new-sha"):
    mock_client = MagicMock()
    get_response = MagicMock()
    get_response.status_code = 404
    mock_client.get.return_value = get_response

    put_response = MagicMock()
    put_response.raise_for_status.return_value = None
    put_response.json.return_value = {"commit": {"sha": new_commit_sha}}
    mock_client.put.return_value = put_response

    context_manager = MagicMock()
    context_manager.__enter__.return_value = mock_client
    context_manager.__exit__.return_value = False
    return context_manager


class TestSlugify:
    def test_lowercases_and_hyphenates(self):
        assert marketing_blog._slugify("Why Custom Websites Beat Template Builders") == (
            "why-custom-websites-beat-template-builders"
        )

    def test_collapses_punctuation_and_trims_edges(self):
        assert marketing_blog._slugify("  --Hello, World!!--  ") == "hello-world"

    def test_empty_title_yields_empty_string(self):
        assert marketing_blog._slugify("###") == ""


class TestUniqueSlug:
    def test_returns_plain_slug_when_free(self, test_db):
        assert marketing_blog.unique_slug(test_db, "Brand New Topic") == "brand-new-topic"

    def test_appends_suffix_when_taken(self, test_db):
        from app.repositories.marketing_blog_post import MarketingBlogPostRepository

        MarketingBlogPostRepository(test_db).create(
            slug="taken-topic", title="Taken Topic", description="", author="MM Nexus", content_blocks=[],
        )
        assert marketing_blog.unique_slug(test_db, "Taken Topic") == "taken-topic-2"

    def test_falls_back_to_post_when_title_slugifies_empty(self, test_db):
        assert marketing_blog.unique_slug(test_db, "###") == "post"


class TestParseFullPost:
    def test_parses_well_formed_response(self):
        raw = (
            "TITLE: Why Manual Reconciliation Is Costing You\n"
            "DESCRIPTION: Manual reconciliation quietly eats hours every week - here's the fix.\n"
            "\n"
            "## The hidden cost\n\nBody text here."
        )
        draft = marketing_blog._parse_full_post(raw, topic_fallback="fallback topic")
        assert draft.title == "Why Manual Reconciliation Is Costing You"
        assert draft.description == "Manual reconciliation quietly eats hours every week - here's the fix."
        assert draft.markdown_body == "## The hidden cost\n\nBody text here."

    def test_falls_back_when_format_not_followed(self):
        raw = "Just a plain response with no structure at all, way over one sixty characters long " * 3
        draft = marketing_blog._parse_full_post(raw, topic_fallback="Process automation for SMEs")
        assert draft.title == "Process automation for SMEs"
        assert len(draft.description) <= 160
        assert draft.markdown_body == raw.strip()

    def test_missing_description_only_falls_back_to_excerpt(self):
        raw = "TITLE: A Real Title\n\nShort body."
        draft = marketing_blog._parse_full_post(raw, topic_fallback="fallback")
        assert draft.title == "A Real Title"
        assert draft.description == "Short body."
        assert draft.markdown_body == "Short body."


class TestGenerateFullPost:
    def test_delegates_to_engine_and_parses_result(self, monkeypatch):
        fake_response = type(
            "R", (), {"reply": "TITLE: Engine Title\nDESCRIPTION: Engine description.\n\nEngine body."}
        )()
        captured = {}

        def _fake_get_engine():
            class _Engine:
                @staticmethod
                def chat(messages, system_prompt):
                    captured["messages"] = messages
                    captured["system_prompt"] = system_prompt
                    return fake_response

            return _Engine()

        monkeypatch.setattr("app.services.marketing_blog.get_engine", _fake_get_engine)

        draft = marketing_blog.generate_full_post("Why SMEs need process automation", tone="direct")
        assert draft.title == "Engine Title"
        assert draft.description == "Engine description."
        assert draft.markdown_body == "Engine body."
        assert "Why SMEs need process automation" in captured["messages"][0]["content"]
        assert "direct" in captured["messages"][0]["content"]
        assert "TITLE:" in captured["system_prompt"]


class TestPublishAndCrossPost:
    def test_website_publish_succeeds_and_linkedin_not_configured(self, test_db, monkeypatch):
        monkeypatch.setattr("app.core.config.settings.marketing_cms_github_pat", "fake-pat")
        monkeypatch.setattr("app.services.marketing_blog.settings.linkedin_organization_access_token", "")
        post = MarketingBlogPostRepository(test_db).create(
            slug="cross-post-test", title="Cross Post Test", description="Desc.", author="MM Nexus",
            content_blocks=[],
        )

        with patch("app.services.marketing_blog.httpx.Client", return_value=_fake_github_client()):
            commit_sha, linkedin_status = marketing_blog.publish_and_cross_post(post, "Body.")

        assert commit_sha == "new-sha"
        assert linkedin_status == "not configured"

    def test_linkedin_failure_does_not_undo_website_publish(self, test_db, monkeypatch):
        monkeypatch.setattr("app.core.config.settings.marketing_cms_github_pat", "fake-pat")
        monkeypatch.setattr("app.services.marketing_blog.settings.linkedin_organization_access_token", "fake-token")
        monkeypatch.setattr("app.services.marketing_blog.settings.linkedin_organization_urn", "urn:li:organization:1")
        post = MarketingBlogPostRepository(test_db).create(
            slug="cross-post-fail-test", title="Cross Post Fail Test", description="Desc.", author="MM Nexus",
            content_blocks=[],
        )

        with patch("app.services.marketing_blog.httpx.Client", return_value=_fake_github_client()):
            commit_sha, linkedin_status = marketing_blog.publish_and_cross_post(post, "Body.")

        assert commit_sha == "new-sha"
        assert linkedin_status.startswith("failed:")


class TestGenerateAndAttachCoverImage:
    def test_happy_path_sets_cover_image_url(self, test_db, monkeypatch):
        monkeypatch.setattr("app.core.config.settings.marketing_cms_github_pat", "fake-pat")
        post = MarketingBlogPostRepository(test_db).create(
            slug="cover-image-test", title="Cover Image Test", description="A test post.", author="MM Nexus",
            content_blocks=[],
        )

        context_manager = _fake_github_client()
        with patch("app.services.marketing_blog.image_gen.generate_cover_image", return_value=b"fake-png") as gen, \
             patch("app.services.marketing_blog.httpx.Client", return_value=context_manager):
            marketing_blog.generate_and_attach_cover_image(post)

        gen.assert_called_once()
        assert "Cover Image Test" in gen.call_args[0][0]
        assert post.cover_image_url == "/blog/covers/cover-image-test.png"
        # Confirm the image bytes were committed to the covers/ path, not the markdown path.
        mock_client = context_manager.__enter__.return_value
        put_call = mock_client.put.call_args
        assert "public/blog/covers/cover-image-test.png" in put_call[0][0]

    def test_image_gen_failure_propagates(self, test_db, monkeypatch):
        from app.integrations.image_gen import ImageGenError

        post = MarketingBlogPostRepository(test_db).create(
            slug="cover-image-fail-test", title="Cover Image Fail Test", description="Desc.", author="MM Nexus",
            content_blocks=[],
        )

        with patch(
            "app.services.marketing_blog.image_gen.generate_cover_image", side_effect=ImageGenError("no key")
        ):
            with pytest.raises(ImageGenError):
                marketing_blog.generate_and_attach_cover_image(post)

        assert post.cover_image_url is None
