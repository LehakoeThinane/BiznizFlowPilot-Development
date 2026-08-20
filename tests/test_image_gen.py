"""Tests for app/integrations/image_gen.py - OpenAI cover-image generation."""

from __future__ import annotations

import base64
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.integrations import image_gen


class TestGenerateCoverImage:
    def test_raises_when_not_configured(self, monkeypatch):
        monkeypatch.setattr("app.integrations.image_gen.settings.openai_api_key", "")
        with pytest.raises(image_gen.ImageGenError):
            image_gen.generate_cover_image("A prompt")

    def test_returns_decoded_bytes_on_success(self, monkeypatch):
        monkeypatch.setattr("app.integrations.image_gen.settings.openai_api_key", "fake-key")
        raw_bytes = b"fake-png-bytes"
        b64 = base64.b64encode(raw_bytes).decode("ascii")

        mock_client = MagicMock()
        response = httpx.Response(
            200,
            json={"data": [{"b64_json": b64}]},
            request=httpx.Request("POST", "https://api.openai.com/v1/images/generations"),
        )
        mock_client.post.return_value = response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch("app.integrations.image_gen.httpx.Client", return_value=mock_client):
            result = image_gen.generate_cover_image("A prompt")

        assert result == raw_bytes

    def test_http_failure_raises_image_gen_error(self, monkeypatch):
        monkeypatch.setattr("app.integrations.image_gen.settings.openai_api_key", "fake-key")

        mock_client = MagicMock()
        mock_client.post.side_effect = httpx.ConnectError("connection refused")
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch("app.integrations.image_gen.httpx.Client", return_value=mock_client):
            with pytest.raises(image_gen.ImageGenError):
                image_gen.generate_cover_image("A prompt")
