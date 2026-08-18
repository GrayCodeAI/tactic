"""thinking.py normalization + env-resolution tests (tau thinking.py port)."""

from __future__ import annotations

import pytest

from agent import thinking


def test_normalize_thinking_level_none_returns_default() -> None:
    assert thinking.normalize_thinking_level(None) == thinking.DEFAULT_THINKING_LEVEL


@pytest.mark.parametrize("level", thinking.THINKING_LEVELS)
def test_normalize_thinking_level_accepts_all_levels(level: str) -> None:
    assert thinking.normalize_thinking_level(level) == level


def test_normalize_thinking_level_is_case_and_whitespace_tolerant() -> None:
    assert thinking.normalize_thinking_level("  HIGH ") == "high"


def test_normalize_thinking_level_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="Unknown thinking mode"):
        thinking.normalize_thinking_level("turbo")


def test_normalize_thinking_levels_rejects_duplicates() -> None:
    with pytest.raises(ValueError, match="unique"):
        thinking.normalize_thinking_levels(["low", "low"])


def test_normalize_thinking_levels_rejects_empty() -> None:
    with pytest.raises(ValueError, match="non-empty list"):
        thinking.normalize_thinking_levels([])


def test_reasoning_effort_maps_off_to_none() -> None:
    assert thinking.reasoning_effort_for_level("off") == "none"
    assert thinking.reasoning_effort_for_level("high") == "high"


def test_anthropic_budget_maps_levels() -> None:
    assert thinking.anthropic_thinking_budget_for_level("off") is None
    assert thinking.anthropic_thinking_budget_for_level("minimal") == 1024
    assert thinking.anthropic_thinking_budget_for_level("xhigh") == 16384


def test_next_thinking_level_cycles() -> None:
    assert thinking.next_thinking_level("off") == "minimal"
    assert thinking.next_thinking_level("xhigh") == "off"
    assert thinking.next_thinking_level("bogus") == "off"


def test_level_from_env_defaults_to_off(monkeypatch) -> None:
    monkeypatch.delenv("PROVER_THINKING", raising=False)
    monkeypatch.setenv("PROVER_DISABLE_THINKING", "1")
    assert thinking.thinking_level_from_env() == "off"


def test_disable_thinking_zero_keeps_default(monkeypatch) -> None:
    monkeypatch.delenv("PROVER_THINKING", raising=False)
    monkeypatch.setenv("PROVER_DISABLE_THINKING", "0")
    # No explicit level and no hard-off switch → default level.
    assert thinking.thinking_level_from_env() == thinking.DEFAULT_THINKING_LEVEL


def test_explicit_prover_thinking_wins_over_disable_switch(monkeypatch) -> None:
    monkeypatch.setenv("PROVER_THINKING", "high")
    monkeypatch.setenv("PROVER_DISABLE_THINKING", "1")
    assert thinking.thinking_level_from_env() == "high"


def test_thinking_enabled_tracks_level(monkeypatch) -> None:
    monkeypatch.setenv("PROVER_THINKING", "medium")
    monkeypatch.delenv("PROVER_DISABLE_THINKING", raising=False)
    assert thinking.thinking_enabled() is True
    assert thinking.thinking_enabled("off") is False


def test_set_thinking_level_overrides_env(monkeypatch) -> None:
    monkeypatch.setenv("PROVER_THINKING", "medium")
    monkeypatch.delenv("PROVER_DISABLE_THINKING", raising=False)
    try:
        assert thinking.set_thinking_level("xhigh") == "xhigh"
        assert thinking.thinking_level_from_env() == "xhigh"
    finally:
        thinking.clear_thinking_level()
    assert thinking.thinking_level_from_env() == "medium"


def test_set_thinking_level_normalizes_and_rejects_invalid() -> None:
    try:
        assert thinking.set_thinking_level("  LOW ") == "low"
        assert thinking.thinking_level_from_env() == "low"
    finally:
        thinking.clear_thinking_level()
    with pytest.raises(ValueError, match="Unknown thinking mode"):
        thinking.set_thinking_level("bogus")
