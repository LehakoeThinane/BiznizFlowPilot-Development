"""Tests for the best-effort website email scraper."""

from __future__ import annotations

import httpx

from app.integrations.email_scraper import find_email


class _FakeResponse:
    def __init__(self, status_code: int, text: str = "", url: str = "", content_type: str = "text/html"):
        self.status_code = status_code
        self.text = text
        self.url = httpx.URL(url or "https://example.co.za")
        self.headers = {"content-type": content_type}


def _mock_get(monkeypatch, responses: list["_FakeResponse | Exception"]):
    """Each call to client.get(...) pops the next queued response/exception, in order."""
    queue = list(responses)

    def _fake_send(self, request, **kwargs):
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(httpx.Client, "send", _fake_send)


def test_finds_mailto_email(monkeypatch):
    html = '<a href="mailto:info@sdlaw.co.za">Email us</a>'
    _mock_get(monkeypatch, [_FakeResponse(200, html, url="https://sdlaw.co.za")])
    assert find_email("https://sdlaw.co.za") == "info@sdlaw.co.za"


def test_finds_plain_text_email(monkeypatch):
    html = "<p>Contact us at hello@lawtons.africa for more info</p>"
    _mock_get(monkeypatch, [_FakeResponse(200, html, url="https://lawtons.africa")])
    assert find_email("https://lawtons.africa") == "hello@lawtons.africa"


def test_prefers_same_domain_email(monkeypatch):
    html = """
    <a href="mailto:webmaster@wixpress.com">template footer</a>
    <p>Reach the team at contact@lawtons.africa</p>
    """
    _mock_get(monkeypatch, [_FakeResponse(200, html, url="https://lawtons.africa")])
    assert find_email("https://lawtons.africa") == "contact@lawtons.africa"


def test_filters_junk_template_domains(monkeypatch):
    html = '<a href="mailto:support@sentry.io">error tracking</a>'
    _mock_get(monkeypatch, [_FakeResponse(200, html, url="https://example-firm.co.za")])
    assert find_email("https://example-firm.co.za") is None


def test_falls_back_to_contact_page(monkeypatch):
    home_html = '<a href="/contact-us">Contact</a>'
    contact_html = "<p>Email: info@fasken.com</p>"
    _mock_get(
        monkeypatch,
        [
            _FakeResponse(200, home_html, url="https://fasken.com"),
            _FakeResponse(200, contact_html, url="https://fasken.com/contact-us"),
        ],
    )
    assert find_email("https://fasken.com") == "info@fasken.com"


def test_returns_none_when_no_email_anywhere(monkeypatch):
    _mock_get(monkeypatch, [_FakeResponse(200, "<p>No contact info here.</p>", url="https://example.co.za")])
    assert find_email("https://example.co.za") is None


def test_returns_none_on_non_200(monkeypatch):
    _mock_get(monkeypatch, [_FakeResponse(404, "not found")])
    assert find_email("https://example.co.za") is None


def test_returns_none_on_non_html_content(monkeypatch):
    _mock_get(monkeypatch, [_FakeResponse(200, "%PDF-1.4", content_type="application/pdf")])
    assert find_email("https://example.co.za") is None


def test_returns_none_on_network_error(monkeypatch):
    _mock_get(monkeypatch, [httpx.ConnectTimeout("timed out")])
    assert find_email("https://example.co.za") is None
