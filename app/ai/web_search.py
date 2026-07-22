"""Perplexity-backed web search, callable as a read-only tool by GroqEngine.

Never raises - a missing key or a failed request both just produce a plain
error string, since this becomes the tool result fed back to the model; the
model can then tell the user web search isn't available rather than the
whole chat turn erroring out.
"""

from __future__ import annotations

import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


def search_web(query: str) -> str:
    if not settings.perplexity_api_key:
        return "Web search is not configured on this server (no Perplexity API key)."

    try:
        resp = httpx.post(
            "https://api.perplexity.ai/chat/completions",
            headers={"Authorization": f"Bearer {settings.perplexity_api_key}"},
            json={
                "model": settings.perplexity_model,
                "messages": [{"role": "user", "content": query}],
            },
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        citations = data.get("citations") or []
        if citations:
            text += "\n\nSources:\n" + "\n".join(f"- {c}" for c in citations)
        return text
    except Exception as exc:
        logger.warning("Perplexity web search failed: %s", exc)
        return f"Web search failed: {exc}"
