"""Unit tests for lemma-bank planning (agent/plan.py).

Mocks llm.chat and lean.compile_only; prove_lemmas is tested with
loop.prove mocked so the sub-loop recursion stays cheap and offline.
"""

from __future__ import annotations

from pathlib import Path

from agent import llm, loop, plan


def _install_chat(monkeypatch, response: str, calls: list | None = None) -> list:
    state = {"n": 0}

    def chat(system, messages, temperature=0.2, retries=4, model_name=None):
        state["n"] += 1
        if calls is not None:
            calls.append((model_name, messages[0]["content"]))
        return llm.LLMResponse(content=response, prompt_tokens=10,
                               completion_tokens=5, total_tokens=15)

    monkeypatch.setattr(plan.llm, "chat", chat)
    return state


def _install_check(monkeypatch, ok: bool = True) -> None:
    def compile_only(file: Path, lean_dir: Path, timeout: int = 60) -> tuple[int, str]:
        return (0, "") if ok else (1, "fake.lean:1:1: error: unknown identifier 'x'\n")

    monkeypatch.setattr(plan.lean, "compile_only", compile_only)


def test_propose_lemmas_returns_verified_statements(tmp_path: Path, monkeypatch) -> None:
    _install_check(monkeypatch, ok=True)
    _install_chat(monkeypatch, """```lean
theorem helper_1 (a b : ℕ) : a + b = b + a := by
  sorry

theorem helper_2 (a : ℕ) : a + 0 = a := by
  sorry
```""")
    lemmas = plan.propose_lemmas("theorem t (a b : ℕ) : a + b = b + a", lean_dir=tmp_path)
    assert len(lemmas) == 2
    assert lemmas[0].startswith("theorem prover_plan_1")
    assert lemmas[1].startswith("theorem prover_plan_2")
    assert all(":= by\n  sorry" in l for l in lemmas)


def test_propose_lemmas_drops_ill_typed(tmp_path: Path, monkeypatch) -> None:
    state = {"n": 0}

    def compile_only(file: Path, lean_dir: Path, timeout: int = 60) -> tuple[int, str]:
        state["n"] += 1
        return (0, "") if state["n"] == 1 else (1, "boom")

    monkeypatch.setattr(plan.lean, "compile_only", compile_only)
    _install_chat(monkeypatch, """```lean
theorem good (a : ℕ) : a = a := by sorry
theorem bad : : := by sorry
```""")
    lemmas = plan.propose_lemmas("theorem t : True", lean_dir=tmp_path)
    assert [l.startswith("theorem prover_plan_") for l in lemmas].count(True) == 1


def test_propose_lemmas_empty_on_llm_error(tmp_path: Path, monkeypatch) -> None:
    _install_chat(monkeypatch, "[LLM error: hard timeout]")
    assert plan.propose_lemmas("theorem t : True", lean_dir=tmp_path) == []


def test_prove_lemmas_keeps_only_proven(monkeypatch) -> None:
    outcomes = iter([True, False])

    def fake_prove(statement, **kwargs):
        proved = next(outcomes)
        return loop.Result(statement=statement, proved=proved, steps=2,
                           seconds=0.1, total_tokens=1, estimated_cost_usd=0.0,
                           proof="  omega")

    monkeypatch.setattr(loop, "prove", fake_prove)
    proven = plan.prove_lemmas(
        ["theorem prover_plan_1 (a b : ℕ) : a + b = b + a := by\n  sorry",
         "theorem prover_plan_2 (a : ℕ) : a = a := by\n  sorry"],
        problem_id="x", max_steps=3,
    )
    assert len(proven) == 1
    assert proven[0].startswith("theorem prover_plan_1")
    assert "omega" in proven[0]
    # non-proven lemma 2 dropped entirely
    assert "prover_plan_2" not in "\n".join(proven)


def test_normalize_lemma_renames_and_strips_proof(tmp_path: Path, monkeypatch) -> None:
    _install_check(monkeypatch, ok=True)
    _install_chat(monkeypatch, "```lean\nlemma my_helper (a : ℕ) : a = a := by\n  rfl\n```")
    lemmas = plan.propose_lemmas("theorem t (a : ℕ) : a = a", lean_dir=tmp_path)
    assert lemmas[0].startswith("theorem prover_plan_1")
    assert "my_helper" not in lemmas[0]
    assert "rfl" not in lemmas[0]
