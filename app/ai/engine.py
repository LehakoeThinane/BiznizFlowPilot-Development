"""LLM engine abstraction.

Supported providers (set AI_PROVIDER in .env):
  echo       — no LLM needed, echoes structured reply (default / dev)
  ollama     — local Ollama server (free, privacy-preserving)
  anthropic  — Anthropic Claude API  (requires ANTHROPIC_API_KEY)
  groq       — Groq fast-inference   (requires GROQ_API_KEY)
"""

from __future__ import annotations

import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

Message = dict[str, str]  # {"role": "user"|"assistant", "content": "..."}


class BaseLLMEngine:
    def chat(self, messages: list[Message], system_prompt: str) -> str:
        raise NotImplementedError


class EchoEngine(BaseLLMEngine):
    """Returns a helpful placeholder — useful when no LLM is configured."""

    def chat(self, messages: list[Message], system_prompt: str) -> str:
        last = messages[-1]["content"] if messages else ""
        return (
            f"[AI not configured — set AI_PROVIDER in .env]\n\n"
            f"You said: {last[:200]}"
        )


class OllamaEngine(BaseLLMEngine):
    """Calls a local Ollama server (http://localhost:11434 by default)."""

    def chat(self, messages: list[Message], system_prompt: str) -> str:
        payload = {
            "model": settings.ollama_model,
            "messages": [{"role": "system", "content": system_prompt}, *messages],
            "stream": False,
            "options": {"num_predict": settings.ai_max_tokens},
        }
        try:
            resp = httpx.post(
                f"{settings.ollama_base_url}/api/chat",
                json=payload,
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["message"]["content"]
        except httpx.ConnectError:
            raise RuntimeError(
                "Cannot reach Ollama. Is it running? Start with: ollama serve"
            )
        except Exception as exc:
            logger.exception("Ollama request failed")
            raise RuntimeError(f"Ollama error: {exc}") from exc


class AnthropicEngine(BaseLLMEngine):
    """Calls Anthropic Claude API."""

    def chat(self, messages: list[Message], system_prompt: str) -> str:
        try:
            import anthropic  # optional dependency
        except ImportError:
            raise RuntimeError(
                "anthropic package not installed. Run: pip install anthropic"
            )

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=settings.ai_max_tokens,
            system=system_prompt,
            messages=messages,
        )
        return response.content[0].text


class GroqEngine(BaseLLMEngine):
    """Calls Groq fast-inference API (OpenAI-compatible)."""

    def chat(self, messages: list[Message], system_prompt: str) -> str:
        try:
            from groq import Groq  # optional dependency
        except ImportError:
            raise RuntimeError(
                "groq package not installed. Run: pip install groq"
            )

        client = Groq(api_key=settings.groq_api_key)
        response = client.chat.completions.create(
            model=settings.groq_model,
            messages=[{"role": "system", "content": system_prompt}, *messages],
            max_tokens=settings.ai_max_tokens,
        )
        return response.choices[0].message.content


def get_engine() -> BaseLLMEngine:
    provider = settings.ai_provider.lower()
    if provider == "ollama":
        return OllamaEngine()
    if provider == "anthropic":
        return AnthropicEngine()
    if provider == "groq":
        return GroqEngine()
    return EchoEngine()
