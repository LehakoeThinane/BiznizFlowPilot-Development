"""Unit tests for the marketing blog service's full-post generation and
slug helpers - the pieces the daily autopublish task needs beyond the
existing generate_content()/publish() covered by test_marketing_cms_blog.py."""

from __future__ import annotations

from app.services import marketing_blog


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
