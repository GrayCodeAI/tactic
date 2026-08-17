"""Tests for model-assisted branch summaries — ported from
huggingface/tau branch_summary coverage, adapted to tactic's LLM client and
event-record sessions."""

from __future__ import annotations

from agent import llm
from agent.branch_summary import (
    BRANCH_SUMMARY_PREAMBLE,
    _serialize_branch_conversation,
    _trim_summary_source_text,
    summarize_branch_with_model,
)


def _records() -> list[dict]:
    return [
        {"t": 1.0, "event": "start", "problem_id": "P1", "statement": "theorem t : 1 = 1 := by rfl"},
        {"t": 2.0, "event": "build", "step": 1, "ok": False, "report": "type mismatch", "diagnostics": 1},
        {"t": 3.0, "event": "goals", "step": 1, "goals": "1 = 1"},
        {"t": 4.0, "event": "llm_response", "step": 1, "body": "rfl"},
        {"t": 5.0, "event": "result", "proved": False, "steps": 1, "seconds": 1.0},
    ]


def test_summarize_empty_history_returns_none() -> None:
    assert summarize_branch_with_model([{"t": 1.0, "event": "start"}]) is None


def test_summarize_failed_llm_returns_none(monkeypatch) -> None:
    def fake_chat(system, messages, **kwargs):
        return llm.LLMResponse(content="[LLM error: nope]", prompt_tokens=0,
                               completion_tokens=0, total_tokens=0)

    monkeypatch.setattr(llm, "chat", fake_chat)
    assert summarize_branch_with_model(_records()) is None


def test_summarize_success_includes_preamble_and_identity(monkeypatch) -> None:
    def fake_chat(system, messages, **kwargs):
        assert "## Goal" in messages[0]["content"]
        assert "theorem t : 1 = 1" in messages[0]["content"]
        return llm.LLMResponse(content="## Goal\nProve t.", prompt_tokens=1,
                               completion_tokens=1, total_tokens=2)

    monkeypatch.setattr(llm, "chat", fake_chat)
    summary = summarize_branch_with_model(_records())
    assert summary is not None
    assert summary.startswith(BRANCH_SUMMARY_PREAMBLE)
    assert "## Goal\nProve t." in summary
    assert "<problem>\nP1\n</problem>" in summary
    assert "<statement>" in summary


def test_summarize_accepts_custom_instructions(monkeypatch) -> None:
    seen: list[str] = []

    def fake_chat(system, messages, **kwargs):
        seen.append(messages[0]["content"])
        return llm.LLMResponse(content="## Goal\nx", prompt_tokens=0,
                               completion_tokens=0, total_tokens=0)

    monkeypatch.setattr(llm, "chat", fake_chat)
    summarize_branch_with_model(_records(), custom_instructions="focus on ring")
    assert "Additional focus: focus on ring" in seen[0]


def test_serialize_branch_conversation_contains_turns() -> None:
    from agent.session_manager import history_from_records

    messages = history_from_records(_records())
    text = _serialize_branch_conversation(messages)
    assert "[User]:" in text
    assert "[Assistant]:" in text
    assert "type mismatch" in text


def test_serialize_truncates_long_content() -> None:
    text = "x" * 10_000
    trimmed = _trim_summary_source_text(text)
    assert len(trimmed) < 10_000
    assert "more characters truncated" in trimmed
    assert _trim_summary_source_text("  ") == "(empty)"


def test_serialize_omits_long_branches(monkeypatch) -> None:
    import agent.branch_summary as bs

    monkeypatch.setattr(bs, "MAX_SUMMARY_SOURCE_TOTAL_CHARS", 200)
    messages = [
        {"role": "user", "content": "a" * 150},
        {"role": "assistant", "content": "b" * 150},
        {"role": "user", "content": "c"},
    ]
    text = _serialize_branch_conversation(messages)
    assert "omitted because the branch was too long" in text
    assert "[User]: c" not in text