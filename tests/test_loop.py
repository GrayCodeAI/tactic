"""Direct unit tests for the proof repair loop (agent/loop.py).

Mocks the Lean toolchain (`lean.check_file`) and the LLM (`llm.chat`)
so the loop's control flow is exercised without Lake/Mathlib or a network
call — the gap the e2e resume tests only brush indirectly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agent import llm, loop

STATEMENT = "theorem prover_loop (n : ℕ) : n + 0 = n := by sorry"

# 10 hammers + 1 failed step-1 check + 1 passing step-2 check
PASS_ON_STEP2 = 12


@pytest.fixture
def hermetic(tmp_path: Path, monkeypatch):
    """Point all ~/.prover writes and the Lean dir at tmp_path."""
    monkeypatch.setenv("PROVER_SESSIONS_DIR", str(tmp_path / "sessions"))
    monkeypatch.setenv("PROVER_LOGS_DIR", str(tmp_path / "logs"))
    monkeypatch.setattr(loop, "LEAN_DIR", tmp_path)
    # Far above any realistic history so auto-compaction never fires via tokens.
    monkeypatch.setattr(llm, "context_window_tokens", lambda: 1_000_000)
    return tmp_path


def install_check(monkeypatch, ok_on: set[int] | None = None) -> dict:
    """Fake `lean.check_file`: fails unless the call number is in ok_on."""
    state = {"calls": 0}

    def fake(_file: Path, _dir: Path) -> tuple[bool, str]:
        state["calls"] += 1
        if ok_on is not None and state["calls"] in ok_on:
            return True, ""
        return False, "fake.lean:1:1: error: goals remain\n"

    monkeypatch.setattr(loop.lean, "check_file", fake)
    return state


def install_chat(monkeypatch, responses: list[str]) -> dict:
    """Fake `llm.chat` returning responses[i] in order (last repeats)."""
    state = {"calls": 0}

    def fake(system: str, messages: list[dict], temperature: float = 0.2,
             retries: int = 4) -> llm.LLMResponse:
        i = min(state["calls"], len(responses) - 1)
        state["calls"] += 1
        return llm.LLMResponse(content=responses[i], prompt_tokens=10,
                               completion_tokens=5, total_tokens=15)

    monkeypatch.setattr(loop.llm, "chat", fake)
    return state


def _event_names(r: loop.Result) -> list[str]:
    return [e["event"] for e in r.trace]


# ---------------------------------------------------------------- hammer pass

def test_hammer_solves_without_llm(hermetic, monkeypatch) -> None:
    """A one-shot hammer that closes the goal never spends LLM tokens."""
    install_check(monkeypatch, ok_on={1})
    chat_state = install_chat(monkeypatch, ["```lean\n  ring\n```"])
    r = loop.prove(STATEMENT, max_steps=5, verbose=False,
                   problem_id="hammer-solve", goal_feedback=False,
                   record_session=False)
    assert r.proved
    assert r.steps == 1
    assert chat_state["calls"] == 0
    names = _event_names(r)
    assert "hammer" in names
    assert "llm_start" not in names
    assert "ring" in r.proof


def test_hammer_solves_after_some_failures(hermetic, monkeypatch) -> None:
    """The hammer pass keeps trying tactics until one closes the goal."""
    install_check(monkeypatch, ok_on={3})  # 3rd hammer (linarith) solves
    chat_state = install_chat(monkeypatch, ["```lean\n  simp\n```"])
    r = loop.prove(STATEMENT, max_steps=5, verbose=False,
                   problem_id="hammer-late", goal_feedback=False,
                   record_session=False)
    assert r.proved
    assert r.steps == 3
    assert chat_state["calls"] == 0
    hammers = [e for e in r.trace if e["event"] == "hammer"]
    assert [h["tactic"] for h in hammers] == ["ring", "omega", "linarith"]
    assert hammers[-1]["ok"] is True


# --------------------------------------------------------------- LLM repairs

def test_llm_repairs_until_build_passes(hermetic, monkeypatch) -> None:
    """Hammers fail → LLM drafts → next build check passes."""
    install_check(monkeypatch, ok_on={PASS_ON_STEP2})
    chat_state = install_chat(monkeypatch, ["```lean\n  ring\n```"])
    r = loop.prove(STATEMENT, max_steps=5, verbose=False,
                   problem_id="llm-repair", goal_feedback=False,
                   record_session=False)
    assert r.proved
    assert r.steps == 2
    assert chat_state["calls"] == 1
    names = _event_names(r)
    assert "llm_start" in names
    assert "llm_request" in names
    assert "llm_response" in names
    build = [e for e in r.trace if e["event"] == "build"]
    assert build[-1]["ok"] is True


def test_llm_error_is_emitted_and_logged(hermetic, monkeypatch,
                                         tmp_path: Path) -> None:
    """An [LLM error …] reply surfaces as an llm_error event and lands in the
    structured failure log; the loop keeps going until the build passes."""
    install_check(monkeypatch, ok_on={PASS_ON_STEP2 + 1})  # one retry turn
    install_chat(monkeypatch,
                 ["[LLM error: 429 rate limited]", "```lean\n  ring\n```"])
    r = loop.prove(STATEMENT, max_steps=5, verbose=False,
                   problem_id="llm-error", goal_feedback=False,
                   record_session=False)
    assert r.proved
    errors = [e for e in r.trace if e["event"] == "llm_error"]
    assert len(errors) == 1
    assert "429" in errors[0]["error"]
    log = tmp_path / "logs" / "agent-calls.jsonl"
    assert log.exists()
    assert '"kind": "llm_error"' in log.read_text()
    assert "429" in log.read_text()


def test_exhausts_max_steps(hermetic, monkeypatch) -> None:
    """A never-solved problem burns the whole budget and reports failure."""
    check_state = install_check(monkeypatch, ok_on=None)
    chat_state = install_chat(monkeypatch, ["```lean\n  simp\n```"])
    r = loop.prove(STATEMENT, max_steps=3, verbose=False,
                   problem_id="exhaust", goal_feedback=False,
                   record_session=False)
    assert not r.proved
    assert r.steps == 3
    assert not r.stopped
    assert chat_state["calls"] == 3
    assert r.total_tokens == 3 * 15
    assert check_state["calls"] == 10 + 3  # 10 hammers + 3 step checks
    result = [e for e in r.trace if e["event"] == "result"][-1]
    assert result["proved"] is False


# --------------------------------------------------------------- control flow

def test_stop_requested_aborts(hermetic, monkeypatch) -> None:
    """should_stop is honored: the run reports stopped and stops early."""
    install_check(monkeypatch, ok_on=None)
    install_chat(monkeypatch, ["```lean\n  simp\n```"])
    r = loop.prove(STATEMENT, max_steps=10, verbose=False,
                   problem_id="stop", goal_feedback=False,
                   record_session=False, should_stop=lambda: True)
    assert not r.proved
    assert r.stopped
    assert r.steps == 0
    result = [e for e in r.trace if e["event"] == "result"][-1]
    assert result["stopped"] is True


def test_skip_hammers_goes_straight_to_llm(hermetic, monkeypatch) -> None:
    """skip_hammers=True: no hammer events, first check is the LLM's sorry."""
    install_check(monkeypatch, ok_on={2})  # step-1 fail + step-2 pass
    chat_state = install_chat(monkeypatch, ["```lean\n  ring\n```"])
    r = loop.prove(STATEMENT, max_steps=5, verbose=False,
                   problem_id="no-hammers", goal_feedback=False,
                   record_session=False, skip_hammers=True)
    assert r.proved
    assert "hammer" not in _event_names(r)
    assert chat_state["calls"] == 1


def test_goal_feedback_emits_goals(hermetic, monkeypatch) -> None:
    """With goal_feedback on, the loop asks the LSP and emits a goals event."""
    install_check(monkeypatch, ok_on={PASS_ON_STEP2})
    install_chat(monkeypatch, ["```lean\n  ring\n```"])

    class FakeLSP:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def update(self, text: str) -> None:
            pass

        def goal_at_end(self, text: str) -> str:
            return "⊢ n + 0 = n"

        def close(self) -> None:
            pass

    monkeypatch.setattr(loop.lsp, "LeanLSP", FakeLSP)
    r = loop.prove(STATEMENT, max_steps=5, verbose=False,
                   problem_id="goals", goal_feedback=True,
                   record_session=False)
    goals = [e for e in r.trace if e["event"] == "goals"]
    assert len(goals) == 1
    assert "⊢ n + 0 = n" in goals[0]["goals"]
    assert r.proved


def test_compaction_event_after_many_failed_steps(hermetic, monkeypatch) -> None:
    """Long runs fold old dead-end turns into a compaction summary (turn-based)."""
    install_check(monkeypatch, ok_on=None)
    chat_state = install_chat(monkeypatch, ["```lean\n  simp\n```"])
    r = loop.prove(STATEMENT, max_steps=22, verbose=False,
                   problem_id="compact", goal_feedback=False,
                   record_session=False)
    assert not r.proved
    assert chat_state["calls"] == 22
    compactions = [e for e in r.trace if e["event"] == "compaction"]
    assert len(compactions) == 1
    assert compactions[0]["dropped"] == 12
    assert r.total_tokens == 22 * 15


# ------------------------------------------------------------------- recording

def test_record_session_writes_jsonl_and_index(hermetic, tmp_path: Path,
                                               monkeypatch) -> None:
    """record_session=True persists the event stream + an index record."""
    install_check(monkeypatch, ok_on={PASS_ON_STEP2})
    install_chat(monkeypatch, ["```lean\n  ring\n```"])
    r = loop.prove(STATEMENT, max_steps=5, verbose=False,
                   problem_id="recorded", goal_feedback=False)
    assert r.session_path is not None
    session_file = Path(r.session_path)
    assert session_file.exists()
    text = session_file.read_text()
    assert '"event": "start"' in text
    assert '"event": "result"' in text
    index = tmp_path / "sessions" / "index.jsonl"
    assert index.exists()
    assert '"status": "proved"' in index.read_text()
