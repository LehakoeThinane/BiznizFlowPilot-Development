"""Tests for GroqEngine's tool-calling loop - mocks groq.Groq the same way
tests/test_email_provider_idempotency.py mocks smtplib.SMTP."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import pytest

from app.ai.engine import GroqEngine


@dataclass
class _FakeFunction:
    name: str
    arguments: str


@dataclass
class _FakeToolCall:
    id: str
    function: _FakeFunction


@dataclass
class _FakeMessage:
    content: str | None = None
    tool_calls: list[_FakeToolCall] | None = None


@dataclass
class _FakeChoice:
    message: _FakeMessage


@dataclass
class _FakeResponse:
    choices: list[_FakeChoice] = field(default_factory=list)


class _FakeCompletions:
    """Returns each entry of `responses` in order, one per .create() call."""

    def __init__(self, responses: list[_FakeResponse]):
        self.responses = list(responses)
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


class _FakeChat:
    def __init__(self, completions: _FakeCompletions):
        self.completions = completions


class _FakeGroqClient:
    def __init__(self, responses: list[_FakeResponse]):
        self.chat = _FakeChat(_FakeCompletions(responses))


def _install_fake_groq(monkeypatch, responses: list[_FakeResponse]) -> _FakeGroqClient:
    client = _FakeGroqClient(responses)
    monkeypatch.setattr("groq.Groq", lambda api_key: client)
    return client


class TestNoToolCalls:
    def test_returns_plain_reply(self, monkeypatch):
        _install_fake_groq(monkeypatch, [
            _FakeResponse(choices=[_FakeChoice(_FakeMessage(content="Hello!"))]),
        ])
        result = GroqEngine().chat([{"role": "user", "content": "hi"}], "system prompt")
        assert result.reply == "Hello!"
        assert result.proposed_actions == []


class TestWebSearchToolCall:
    def test_executes_inline_and_loops(self, monkeypatch):
        client = _install_fake_groq(monkeypatch, [
            _FakeResponse(choices=[_FakeChoice(_FakeMessage(
                content=None,
                tool_calls=[_FakeToolCall("call_1", _FakeFunction("web_search", json.dumps({"query": "weather today"})))],
            ))]),
            _FakeResponse(choices=[_FakeChoice(_FakeMessage(content="It's sunny."))]),
        ])
        monkeypatch.setattr("app.ai.web_search.search_web", lambda query: f"Result for: {query}")

        result = GroqEngine().chat([{"role": "user", "content": "what's the weather"}], "system")

        assert result.reply == "It's sunny."
        assert result.proposed_actions == []
        assert len(client.chat.completions.calls) == 2
        second_call_messages = client.chat.completions.calls[1]["messages"]
        tool_msg = next(m for m in second_call_messages if m.get("role") == "tool")
        assert tool_msg["content"] == "Result for: weather today"
        assert tool_msg["tool_call_id"] == "call_1"

    def test_search_web_raising_is_caught_and_fed_back_as_tool_result(self, monkeypatch):
        client = _install_fake_groq(monkeypatch, [
            _FakeResponse(choices=[_FakeChoice(_FakeMessage(
                content=None,
                tool_calls=[_FakeToolCall("call_1", _FakeFunction("web_search", json.dumps({"query": "x"})))],
            ))]),
            _FakeResponse(choices=[_FakeChoice(_FakeMessage(content="Sorry, search is unavailable."))]),
        ])

        def _boom(query):
            raise RuntimeError("search backend down")

        monkeypatch.setattr("app.ai.web_search.search_web", _boom)

        result = GroqEngine().chat([{"role": "user", "content": "search something"}], "system")

        assert result.reply == "Sorry, search is unavailable."
        second_call_messages = client.chat.completions.calls[1]["messages"]
        tool_msg = next(m for m in second_call_messages if m.get("role") == "tool")
        assert "Tool execution error" in tool_msg["content"]
        assert "search backend down" in tool_msg["content"]


class TestMutatingToolCall:
    def test_stops_and_proposes_action(self, monkeypatch):
        _install_fake_groq(monkeypatch, [
            _FakeResponse(choices=[_FakeChoice(_FakeMessage(
                content=None,
                tool_calls=[_FakeToolCall(
                    "call_1",
                    _FakeFunction("create_task", json.dumps({
                        "title": "Follow up with Acme", "summary": "Create a follow-up task for Acme.",
                    })),
                )],
            ))]),
        ])

        result = GroqEngine().chat([{"role": "user", "content": "create a task"}], "system")

        assert len(result.proposed_actions) == 1
        action = result.proposed_actions[0]
        assert action.action_type == "create_task"
        assert action.description == "Create a follow-up task for Acme."
        assert action.arguments == {"title": "Follow up with Acme"}  # summary popped out
        assert "Create a follow-up task for Acme." in result.reply

    def test_mixed_batch_proposes_only_mutating_calls(self, monkeypatch):
        _install_fake_groq(monkeypatch, [
            _FakeResponse(choices=[_FakeChoice(_FakeMessage(
                content=None,
                tool_calls=[
                    _FakeToolCall("call_1", _FakeFunction("web_search", json.dumps({"query": "x"}))),
                    _FakeToolCall("call_2", _FakeFunction("create_task", json.dumps({"title": "T", "summary": "S"}))),
                ],
            ))]),
        ])

        result = GroqEngine().chat([{"role": "user", "content": "do things"}], "system")

        assert len(result.proposed_actions) == 1
        assert result.proposed_actions[0].action_type == "create_task"

    def test_malformed_json_arguments_is_skipped_not_crashed(self, monkeypatch):
        _install_fake_groq(monkeypatch, [
            _FakeResponse(choices=[_FakeChoice(_FakeMessage(
                content=None,
                tool_calls=[_FakeToolCall("call_1", _FakeFunction("create_task", "{not valid json"))],
            ))]),
        ])

        result = GroqEngine().chat([{"role": "user", "content": "create a task"}], "system")

        assert result.proposed_actions == []


class TestIterationCap:
    def test_terminates_with_fallback_reply(self, monkeypatch):
        responses = [
            _FakeResponse(choices=[_FakeChoice(_FakeMessage(
                content=None,
                tool_calls=[_FakeToolCall(f"call_{i}", _FakeFunction("web_search", json.dumps({"query": "x"})))],
            ))])
            for i in range(10)
        ]
        _install_fake_groq(monkeypatch, responses)
        monkeypatch.setattr("app.ai.web_search.search_web", lambda query: "some result")

        result = GroqEngine().chat([{"role": "user", "content": "research forever"}], "system")

        assert "wasn't able to finish" in result.reply
        assert result.proposed_actions == []


class TestMissingGroqPackage:
    def test_raises_runtime_error_when_groq_not_installed(self, monkeypatch):
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "groq":
                raise ImportError("no groq")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        with pytest.raises(RuntimeError, match="groq package not installed"):
            GroqEngine().chat([{"role": "user", "content": "hi"}], "system")
