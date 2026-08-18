"""proof-loop → diagnostics wiring: an LLM failure appends a JSONL entry."""

from __future__ import annotations

import json

import pytest

from agent import llm, loop


@pytest.fixture
def failing_llm(monkeypatch):
    """LLM that always answers with an error (forces the llm_error path)."""

    def fake_chat(system, messages, temperature=0.2, retries=4):
        return llm.LLMResponse(content="[LLM error: 429 rate limit]")

    monkeypatch.setattr(llm, "chat", fake_chat)


def test_llm_error_writes_diagnostic_log(failing_llm, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("TACTIC_LOGS_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("TACTIC_SESSIONS_DIR", str(tmp_path / "sessions"))
    # Skip the real Lean build so the test doesn't need a toolchain.
    monkeypatch.setattr(loop.lean, "check_file", lambda *a, **k: (False, "fake.lean:1:0: error"))
    monkeypatch.setattr(loop.lean, "parse_diagnostics", lambda *a, **k: [])
    monkeypatch.setattr(loop.lean, "error_report", lambda *a, **k: "fake report")

    r = loop.prove(
        "theorem tactic_diag (n : ℕ) : n + 0 = n := by\n  sorry",
        max_steps=1, verbose=False, problem_id="diag-wire",
        goal_feedback=False, skip_hammers=True,
    )

    assert r.proved is False
    log = tmp_path / "logs" / "agent-calls.jsonl"
    assert log.exists()
    entries = [json.loads(line) for line in log.read_text().splitlines() if line.strip()]
    llm_errors = [e for e in entries if e["kind"] == "llm_error"]
    assert llm_errors, entries
    entry = llm_errors[0]
    assert entry["problem_id"] == "diag-wire"
    assert entry["error"]["status_code"] == 429
