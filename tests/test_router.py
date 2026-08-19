"""Unit tests for per-difficulty routing (agent/router.py)."""

from __future__ import annotations

from agent import router


def test_select_defaults_to_active_model(monkeypatch) -> None:
    monkeypatch.delenv("PROVER_MODEL", raising=False)
    monkeypatch.delenv("PROVER_MODEL_EASY", raising=False)
    monkeypatch.delenv("PROVER_TEMP_EASY", raising=False)
    monkeypatch.delenv("PROVER_STEPS_EASY", raising=False)
    monkeypatch.setattr(router.llm, "model", lambda: "gpt-4o")
    cfg = router.select("easy")
    assert cfg["model"] == "gpt-4o"
    assert "temperature" not in cfg
    assert "max_steps" not in cfg


def test_select_none_difficulty_uses_generic(monkeypatch) -> None:
    monkeypatch.setattr(router.llm, "model", lambda: "gpt-4o")
    monkeypatch.delenv("PROVER_MODEL", raising=False)
    assert router.select(None)["model"] == "gpt-4o"
    assert router.select("")["model"] == "gpt-4o"


def test_select_tier_env_overrides(monkeypatch) -> None:
    monkeypatch.setenv("PROVER_MODEL_HARD", "deepseek-r1")
    monkeypatch.setenv("PROVER_TEMP_HARD", "0.9")
    monkeypatch.setenv("PROVER_STEPS_HARD", "40")
    monkeypatch.setattr(router.llm, "model", lambda: "gpt-4o")
    cfg = router.select("hard", model="fallback")
    assert cfg == {"model": "deepseek-r1", "temperature": 0.9, "max_steps": 40}


def test_select_explicit_model_fallback(monkeypatch) -> None:
    monkeypatch.delenv("PROVER_MODEL", raising=False)
    monkeypatch.delenv("PROVER_MODEL_MEDIUM", raising=False)
    cfg = router.select("medium", model="qwen-27b")
    assert cfg["model"] == "qwen-27b"


def test_select_malformed_env_ignored(monkeypatch) -> None:
    monkeypatch.setenv("PROVER_TEMP_EASY", "not-a-number")
    monkeypatch.setenv("PROVER_STEPS_EASY", "lots")
    cfg = router.select("easy")
    assert "temperature" not in cfg
    assert "max_steps" not in cfg


def test_select_tier_names_are_case_insensitive(monkeypatch) -> None:
    monkeypatch.setenv("PROVER_MODEL_TRIVIAL", "tiny-model")
    assert router.select("Trivial")["model"] == "tiny-model"
