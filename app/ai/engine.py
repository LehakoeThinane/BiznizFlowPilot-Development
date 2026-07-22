"""LLM engine abstraction.

Supported providers (set AI_PROVIDER in .env):
  echo       — no LLM needed, echoes structured reply (default / dev)
  ollama     — local Ollama server (free, privacy-preserving)
  anthropic  — Anthropic Claude API  (requires ANTHROPIC_API_KEY)
  groq       — Groq fast-inference   (requires GROQ_API_KEY) - the only
               engine with tool-calling (co-pilot actions + web search)
"""

from __future__ import annotations

import json
import logging

import httpx

from app.ai.action_types import EngineResponse, ProposedAction
from app.core.config import settings

logger = logging.getLogger(__name__)

Message = dict[str, str]  # {"role": "user"|"assistant", "content": "..."}

_MAX_TOOL_ITERATIONS = 4


class BaseLLMEngine:
    def chat(self, messages: list[Message], system_prompt: str) -> EngineResponse:
        raise NotImplementedError


class EchoEngine(BaseLLMEngine):
    """Returns a helpful placeholder — useful when no LLM is configured."""

    def chat(self, messages: list[Message], system_prompt: str) -> EngineResponse:
        last = messages[-1]["content"] if messages else ""
        return EngineResponse(
            reply=(
                f"[AI not configured — set AI_PROVIDER in .env]\n\n"
                f"You said: {last[:200]}"
            )
        )


class OllamaEngine(BaseLLMEngine):
    """Calls a local Ollama server (http://localhost:11434 by default)."""

    def chat(self, messages: list[Message], system_prompt: str) -> EngineResponse:
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
            return EngineResponse(reply=data["message"]["content"])
        except httpx.ConnectError:
            raise RuntimeError(
                "Cannot reach Ollama. Is it running? Start with: ollama serve"
            )
        except Exception as exc:
            logger.exception("Ollama request failed")
            raise RuntimeError(f"Ollama error: {exc}") from exc


class AnthropicEngine(BaseLLMEngine):
    """Calls Anthropic Claude API."""

    def chat(self, messages: list[Message], system_prompt: str) -> EngineResponse:
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
        return EngineResponse(reply=response.content[0].text)


class GroqEngine(BaseLLMEngine):
    """Calls Groq fast-inference API (OpenAI-compatible), with tool-calling
    for co-pilot actions and web search.

    Policy for a turn whose tool_calls mix read-only (web_search) and
    mutating (create_task/etc.) calls: stop immediately and propose only the
    mutating ones, executing none of the read-only ones from that turn. The
    OpenAI/Groq wire format requires a tool-result message for every
    tool_call in the preceding assistant message before the conversation can
    continue, so partially executing a batch produces an awkward
    half-finished turn - proposing the whole batch and letting the user
    confirm (or the next turn re-ask) is the simplest correct v1 behavior.
    """

    def chat(self, messages: list[Message], system_prompt: str) -> EngineResponse:
        try:
            from groq import Groq  # optional dependency
        except ImportError:
            raise RuntimeError(
                "groq package not installed. Run: pip install groq"
            )

        from app.ai.tools import MUTATING_ACTION_TYPES, TOOL_SCHEMAS
        from app.ai.web_search import search_web

        client = Groq(api_key=settings.groq_api_key)
        api_messages: list[dict] = [{"role": "system", "content": system_prompt}, *messages]

        for _ in range(_MAX_TOOL_ITERATIONS):
            response = client.chat.completions.create(
                model=settings.groq_model,
                messages=api_messages,
                max_tokens=settings.ai_max_tokens,
                tools=TOOL_SCHEMAS,
                tool_choice="auto",
            )
            choice = response.choices[0].message
            tool_calls = choice.tool_calls or []

            if not tool_calls:
                return EngineResponse(reply=choice.content or "")

            mutating_calls = [tc for tc in tool_calls if tc.function.name in MUTATING_ACTION_TYPES]
            if mutating_calls:
                proposed: list[ProposedAction] = []
                for tc in mutating_calls:
                    try:
                        args = json.loads(tc.function.arguments)
                    except (json.JSONDecodeError, TypeError):
                        continue
                    summary = args.pop("summary", f"Run {tc.function.name}")
                    proposed.append(ProposedAction(action_type=tc.function.name, arguments=args, description=summary))
                reply_text = choice.content or (
                    "I've prepared the following action(s) for your review:\n"
                    + "\n".join(f"- {p.description}" for p in proposed)
                )
                return EngineResponse(reply=reply_text, proposed_actions=proposed)

            # All tool_calls this turn are read-only (web_search) - execute inline and loop.
            api_messages.append(
                {
                    "role": "assistant",
                    "content": choice.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                        }
                        for tc in tool_calls
                    ],
                }
            )
            for tc in tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                    result_text = search_web(args.get("query", ""))
                except Exception as exc:
                    result_text = f"Tool execution error: {exc}"
                api_messages.append({"role": "tool", "tool_call_id": tc.id, "content": result_text})

        return EngineResponse(reply="I wasn't able to finish researching that in time — please try rephrasing.")


def get_engine() -> BaseLLMEngine:
    provider = settings.ai_provider.lower()
    if provider == "ollama":
        return OllamaEngine()
    if provider == "anthropic":
        return AnthropicEngine()
    if provider == "groq":
        return GroqEngine()
    return EchoEngine()
