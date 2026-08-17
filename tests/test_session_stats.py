"""Session stats tests — ported from huggingface/tau tests for session_stats,
adapted to tactic's JSONL event stream (a result event carries the totals)."""

from __future__ import annotations

from agent.session_stats import SessionStats, calculate_session_stats


def test_empty_records() -> None:
    stats = calculate_session_stats([])
    assert stats == SessionStats()
    assert stats.turn_count == 0
    assert stats.steps == 0
    assert stats.total_tokens == 0


def test_llm_requests_count_as_turns() -> None:
    records = [
        {"event": "llm_request", "step": 1},
        {"event": "llm_response", "step": 1, "prompt_tokens": 10, "completion_tokens": 5,
         "tokens": 15},
        {"event": "llm_request", "step": 2},
    ]
    stats = calculate_session_stats(records)
    assert stats.turn_count == 2
    assert stats.input_tokens == 10
    assert stats.output_tokens == 5
    assert stats.total_tokens == 15


def test_result_event_overrides_totals() -> None:
    records = [
        {"event": "llm_request", "step": 1},
        {"event": "llm_response", "step": 1, "prompt_tokens": 100, "completion_tokens": 50,
         "tokens": 150},
        {"event": "result", "proved": False, "steps": 12, "seconds": 600.0,
         "prompt_tokens": 900, "completion_tokens": 100, "total_tokens": 1000,
         "cost_usd": 0.0042},
    ]
    stats = calculate_session_stats(records)
    assert stats.turn_count == 1
    assert stats.steps == 12
    assert stats.input_tokens == 900
    assert stats.output_tokens == 100
    assert stats.total_tokens == 1000
    assert stats.estimated_cost == 0.0042


def test_result_event_without_token_fields() -> None:
    records = [{"event": "result", "proved": True, "steps": 2}]
    stats = calculate_session_stats(records)
    assert stats.steps == 2
    assert stats.total_tokens == 0
