"""Unit tests for autoformalization (agent/formalize.py).

Mocks llm.chat and lean.compile_only so no network / Lake is needed. The
retry-on-diagnostics loop, response normalization, and terminal failure are
covered.
"""

from __future__ import annotations

from pathlib import Path

from agent import formalize, llm

STATEMENT = "For all natural numbers n, the sum of the first n natural numbers equals n(n+1)/2."


def _install_chat(monkeypatch, responses: list[str]) -> list[list[dict]]:
    seen: list[list[dict]] = []

    def chat(system, messages, temperature=0.2, retries=4, model_name=None):
        seen.append(messages)
        return llm.LLMResponse(content=responses[min(len(seen) - 1, len(responses) - 1)],
                               prompt_tokens=10, completion_tokens=5, total_tokens=15)

    monkeypatch.setattr(formalize.llm, "chat", chat)
    return seen


def _install_check(monkeypatch, ok_on: set[int]) -> None:
    state = {"calls": 0}

    def compile_only(file: Path, lean_dir: Path, timeout: int = 60) -> tuple[int, str]:
        state["calls"] += 1
        if state["calls"] in ok_on:
            return 0, ""
        return 1, "fake.lean:1:1: error: unknown identifier 'foo'\n"

    monkeypatch.setattr(formalize.lean, "compile_only", compile_only)
    return state


def test_formalize_success_normalizes_statement(tmp_path: Path, monkeypatch) -> None:
    _install_check(monkeypatch, ok_on={1})
    _install_chat(monkeypatch, [
        "```lean\ntheorem my_sum (n : ℕ) : (∑ i ∈ range (n + 1), i) = n * (n + 1) / 2 := by\n  sorry\n```",
    ])
    r = formalize.formalize(STATEMENT, lean_dir=tmp_path)
    assert r.ok
    assert r.attempts == 1
    assert r.statement.startswith("theorem prover_formal_1")
    assert ":= by\n  sorry" in r.statement
    assert "my_sum" not in r.statement


def test_formalize_retries_on_compile_failure(tmp_path: Path, monkeypatch) -> None:
    _install_check(monkeypatch, ok_on={2})
    _install_chat(monkeypatch, [
        "```lean\ntheorem wrong : 1 = 2 := by sorry\n```",
        "```lean\ntheorem right (n : ℕ) : n + 0 = n := by\n  sorry\n```",
    ])
    r = formalize.formalize(STATEMENT, lean_dir=tmp_path)
    assert r.ok
    assert r.attempts == 2
    # second attempt saw the diagnostics
    assert "unknown identifier 'foo'" in r.history[2]["content"]


def test_formalize_gives_up_after_max_attempts(tmp_path: Path, monkeypatch) -> None:
    _install_check(monkeypatch, ok_on=set())
    _install_chat(monkeypatch, ["```lean\ntheorem bad : : := by sorry\n```"])
    r = formalize.formalize(STATEMENT, max_attempts=3, lean_dir=tmp_path)
    assert not r.ok
    assert r.attempts == 3
    assert r.diagnostics


def test_formalize_no_theorem_in_response(tmp_path: Path, monkeypatch) -> None:
    _install_check(monkeypatch, ok_on=set())
    _install_chat(monkeypatch, ["This is not formalizable as stated."])
    r = formalize.formalize(STATEMENT, lean_dir=tmp_path)
    assert not r.ok
    assert "did not produce a theorem" in r.diagnostics


def test_formalize_llm_error_reported_and_continues(tmp_path: Path, monkeypatch) -> None:
    _install_check(monkeypatch, ok_on={1})  # attempt 2 is the first compile call
    _install_chat(monkeypatch, [
        "[LLM error: hard timeout]",
        "```lean\ntheorem ok (n : ℕ) : n = n := by\n  sorry\n```",
    ])
    r = formalize.formalize(STATEMENT, lean_dir=tmp_path)
    assert r.ok
    assert r.attempts == 2
