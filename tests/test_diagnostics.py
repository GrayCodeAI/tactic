"""diagnostics.py structured failure-log tests (tau diagnostics.py port)."""

from __future__ import annotations

import json
from pathlib import Path

from agent.diagnostics import (
    ProofCallDiagnosticContext,
    ProofCallDiagnosticLogger,
    new_proof_call_run_id,
)
from agent.paths import ProverPaths


def _context(tmp_path: Path) -> ProofCallDiagnosticContext:
    return ProofCallDiagnosticContext(
        model="test-model",
        cwd=tmp_path,
        session_id="sess-1",
        run_id="run-1",
        problem_id="p1",
    )


def test_log_exception_writes_jsonl_entry(tmp_path: Path) -> None:
    logger = ProofCallDiagnosticLogger(tmp_path / "logs" / "agent-calls.jsonl")
    try:
        raise RuntimeError("boom")
    except RuntimeError as exc:
        path = logger.log_exception(context=_context(tmp_path), phase="step-1", exc=exc)
    assert path is not None and path.exists()
    entry = json.loads(path.read_text().splitlines()[0])
    assert entry["kind"] == "exception"
    assert entry["phase"] == "step-1"
    assert entry["run_id"] == "run-1"
    assert entry["session_id"] == "sess-1"
    assert entry["exception"]["type"] == "RuntimeError"
    assert "boom" in entry["exception"]["traceback"]


def test_log_llm_error_extracts_status_and_attempts(tmp_path: Path) -> None:
    logger = ProofCallDiagnosticLogger(tmp_path / "agent-calls.jsonl")
    logger.log_llm_error(
        context=_context(tmp_path), phase="step-2",
        error="[LLM error: 429 rate limit]", attempt=3,
    )
    entry = json.loads(logger.path.read_text().splitlines()[0])
    assert entry["kind"] == "llm_error"
    assert entry["error"]["status_code"] == 429
    assert entry["error"]["attempts"] == 3


def test_from_paths_uses_logs_dir(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PROVER_LOGS_DIR", str(tmp_path / "custom-logs"))
    logger = ProofCallDiagnosticLogger.from_paths()
    assert logger.path == tmp_path / "custom-logs" / "agent-calls.jsonl"


def test_from_paths_default_layout(tmp_path: Path) -> None:
    paths = ProverPaths(home=tmp_path / "home")
    logger = ProofCallDiagnosticLogger.from_paths(paths)
    assert logger.path == tmp_path / "home" / "logs" / "agent-calls.jsonl"


def test_log_returns_none_when_path_unwritable(tmp_path: Path) -> None:
    # Parent is a file, not a dir → mkdir raises OSError → silent no-op.
    blocker = tmp_path / "block"
    blocker.write_text("x")
    logger = ProofCallDiagnosticLogger(blocker / "agent-calls.jsonl")
    result = logger.log_llm_error(context=_context(tmp_path), phase="step-1", error="x")
    assert result is None


def test_new_run_id_is_unique() -> None:
    assert new_proof_call_run_id() != new_proof_call_run_id()
