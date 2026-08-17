"""context_window token estimation + threshold tests (tau port shape)."""

from __future__ import annotations

from agent.context_window import (
    ContextUsageEstimate,
    auto_compaction_threshold_for_context_window,
    estimate_context_tokens,
    estimate_context_usage,
    estimate_message_tokens,
    estimate_text_tokens,
)


def test_estimate_text_tokens_floor_and_rounding() -> None:
    assert estimate_text_tokens("") == 0
    assert estimate_text_tokens("hello") == 2  # ceil(5/4)=2, but floored to max(1,..)
    assert estimate_text_tokens("helloooooooooooooooo") == 5  # 18 chars -> ceil(18/4)=5


def test_estimate_message_tokens_user_and_assistant() -> None:
    user = {"role": "user", "content": "abcd"}
    asst = {"role": "assistant", "content": "efgh", "tool_calls": [{"name": "f", "arguments": "x=1"}]}
    tm = estimate_message_tokens(user)
    am = estimate_message_tokens(asst)
    assert tm == 4 + 1  # overhead 4 + ceil(4/4)=1
    # assistant: overhead 4 + ceil(4/4)=1 + tool-call overhead 16 + ceil(4/4) for
    # name("f")+arguments("x=1")="fx=1" (4 chars)
    assert am == 4 + 1 + 16 + 1


def test_estimate_context_tokens_sums_messages() -> None:
    history = [{"role": "user", "content": "abcd"}, {"role": "assistant", "content": "efgh"}]
    assert estimate_context_tokens("sys", history) == estimate_context_usage(
        "sys", history
    ).total_tokens


def test_context_usage_breakdown() -> None:
    history = [{"role": "tool", "name": "lean", "content": "ok"}]
    est = estimate_context_usage("system prompt", history)
    assert isinstance(est, ContextUsageEstimate)
    assert est.message_count == 1
    assert est.system_tokens == estimate_text_tokens("system prompt")


def test_auto_compaction_threshold_tau_shape() -> None:
    from agent.llm import DEFAULT_COMPACTION_RESERVE_TOKENS

    assert auto_compaction_threshold_for_context_window(128_000) == 128_000 - DEFAULT_COMPACTION_RESERVE_TOKENS
    assert auto_compaction_threshold_for_context_window(0) is None
    assert auto_compaction_threshold_for_context_window(-1) is None
