"""Tests for app/ai/web_search.py's Perplexity tool executor."""

from __future__ import annotations

import httpx

from app.ai.web_search import search_web


class _FakeResponse:
    def __init__(self, json_data: dict, status_code: int = 200):
        self._json = json_data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=self)

    def json(self):
        return self._json


class TestSearchWeb:
    def test_missing_api_key_short_circuits_no_http_call(self, monkeypatch):
        monkeypatch.setattr("app.ai.web_search.settings.perplexity_api_key", "")
        called = []
        monkeypatch.setattr("httpx.post", lambda *a, **kw: called.append(1))

        result = search_web("anything")

        assert "not configured" in result
        assert called == []

    def test_success_appends_citations(self, monkeypatch):
        monkeypatch.setattr("app.ai.web_search.settings.perplexity_api_key", "fake-key")
        monkeypatch.setattr(
            "httpx.post",
            lambda *a, **kw: _FakeResponse({
                "choices": [{"message": {"content": "The answer is 42."}}],
                "citations": ["https://example.com/a", "https://example.com/b"],
            }),
        )

        result = search_web("what is the answer")

        assert "The answer is 42." in result
        assert "https://example.com/a" in result
        assert "https://example.com/b" in result

    def test_success_without_citations(self, monkeypatch):
        monkeypatch.setattr("app.ai.web_search.settings.perplexity_api_key", "fake-key")
        monkeypatch.setattr(
            "httpx.post",
            lambda *a, **kw: _FakeResponse({"choices": [{"message": {"content": "Just text."}}]}),
        )

        result = search_web("query")

        assert result == "Just text."

    def test_request_failure_returns_graceful_error(self, monkeypatch):
        monkeypatch.setattr("app.ai.web_search.settings.perplexity_api_key", "fake-key")

        def _raise(*a, **kw):
            raise httpx.ConnectError("connection refused")

        monkeypatch.setattr("httpx.post", _raise)

        result = search_web("query")

        assert "Web search failed" in result
