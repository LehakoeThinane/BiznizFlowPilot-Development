"""Tests for app/integrations/linkedin.py's company-page posting stub."""

from __future__ import annotations

import pytest

from app.integrations import linkedin


class TestPostCompanyUpdate:
    def test_returns_none_when_not_configured(self, monkeypatch):
        monkeypatch.setattr("app.integrations.linkedin.settings.linkedin_organization_access_token", "")
        monkeypatch.setattr("app.integrations.linkedin.settings.linkedin_organization_urn", "")
        assert linkedin.post_company_update("Some text", "https://mmnexus.co.za/blog/some-post") is None

    def test_raises_when_configured_but_not_implemented(self, monkeypatch):
        monkeypatch.setattr("app.integrations.linkedin.settings.linkedin_organization_access_token", "fake-token")
        monkeypatch.setattr("app.integrations.linkedin.settings.linkedin_organization_urn", "urn:li:organization:1")
        with pytest.raises(linkedin.LinkedInPostError):
            linkedin.post_company_update("Some text", "https://mmnexus.co.za/blog/some-post")
