"""llm._call thinking-level → provider kwargs tests (tau thinking wiring port)."""

from __future__ import annotations

from typing import ClassVar

import pytest

from agent import llm


class _FakeMessage:
    content = "ok"
    reasoning = None


class _FakeChoice:
    message = _FakeMessage()


class _FakeResponse:
    choices: ClassVar = [_FakeChoice()]
    usage = None


class _FakeCompletions:
    def __init__(self) -> None:
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return _FakeResponse()


class _FakeChat:
    def __init__(self) -> None:
        self.completions = _FakeCompletions()


class _FakeClient:
    def __init__(self) -> None:
        self.chat = _FakeChat()


@pytest.fixture
def fake_client(monkeypatch):
    client = _FakeClient()

    def _client():
        return client

    monkeypatch.setattr(llm, "client", _client)
    return client


def test_thinking_off_with_base_url_sends_disable_switch(monkeypatch, fake_client) -> None:
    monkeypatch.delenv("PROVER_THINKING", raising=False)
    monkeypatch.setenv("PROVER_DISABLE_THINKING", "1")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:1/v1")
    llm._call("sys", [], 0.2)
    kwargs = fake_client.chat.completions.kwargs
    assert kwargs["extra_body"] == {"chat_template_kwargs": {"enable_thinking": False}}
    assert "reasoning_effort" not in kwargs


def test_thinking_off_without_base_url_sends_nothing(monkeypatch, fake_client) -> None:
    monkeypatch.delenv("PROVER_THINKING", raising=False)
    monkeypatch.setenv("PROVER_DISABLE_THINKING", "1")
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    llm._call("sys", [], 0.2)
    kwargs = fake_client.chat.completions.kwargs
    assert "extra_body" not in kwargs
    assert "reasoning_effort" not in kwargs


def test_explicit_thinking_level_sends_reasoning_effort(monkeypatch, fake_client) -> None:
    monkeypatch.setenv("PROVER_THINKING", "high")
    monkeypatch.delenv("PROVER_DISABLE_THINKING", raising=False)
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:1/v1")
    llm._call("sys", [], 0.2)
    kwargs = fake_client.chat.completions.kwargs
    assert kwargs["reasoning_effort"] == "high"
    assert "extra_body" not in kwargs
