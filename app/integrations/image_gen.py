"""AI cover-image generation for marketing blog posts - OpenAI's Images API
(DALL-E 3). Returns raw image bytes - callers are responsible for storing
them somewhere permanent (see app/services/marketing_blog.py's
publish_cover_image(), which commits into MM-Nexus-Website's own repo
rather than a presigned-URL object store, since a blog's cover image
needs to keep working indefinitely, not for a few minutes)."""

from __future__ import annotations

import base64

import httpx

from app.core.config import settings


class ImageGenError(Exception):
    """Raised when OpenAI isn't configured, or the image generation call fails."""


def generate_cover_image(prompt: str) -> bytes:
    """Generate one landscape (1792x1024) image from a text prompt, returns
    raw PNG bytes."""
    if not settings.openai_api_key:
        raise ImageGenError("OPENAI_API_KEY is not configured.")

    try:
        with httpx.Client(timeout=60) as client:
            resp = client.post(
                "https://api.openai.com/v1/images/generations",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                json={
                    "model": "dall-e-3",
                    "prompt": prompt,
                    "size": "1792x1024",
                    "quality": "standard",
                    "n": 1,
                    "response_format": "b64_json",
                },
            )
            resp.raise_for_status()
            b64_data = resp.json()["data"][0]["b64_json"]
            return base64.b64decode(b64_data)
    except httpx.HTTPError as exc:
        raise ImageGenError(f"Failed to generate cover image: {exc}") from exc
