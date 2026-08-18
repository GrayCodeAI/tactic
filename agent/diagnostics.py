"""Structured diagnostic logging for proof-session failures (tau diagnostics.py port).

Prover's llm_error events already keep the human-readable stream; this module
adds tau's machine-readable JSONL failure log under `ProverPaths.logs_dir`
(`~/.prover/logs/agent-calls.jsonl`) so hard failures (timeouts, 5xx, malformed
responses) survive a TUI restart with full tracebacks.
"""

from __future__ import annotations

import json
import traceback
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from .paths import ProverPaths


@dataclass(frozen=True, slots=True)
class ProofCallDiagnosticContext:
    """Non-secret context attached to one diagnostic entry (tau's AgentCallDiagnosticContext)."""

    model: str
    cwd: Path
    session_id: str | None
    run_id: str
    problem_id: str | None = None


class ProofCallDiagnosticLogger:
    """Append structured JSONL diagnostics for proof-loop failures (tau's AgentCallDiagnosticLogger)."""

    def __init__(self, path: Path) -> None:
        self.path = path

    @classmethod
    def from_paths(cls, paths: ProverPaths | None = None) -> ProofCallDiagnosticLogger:
        """Create a logger using prover's default path layout."""
        return cls((paths or ProverPaths()).logs_dir / "agent-calls.jsonl")

    def log_exception(
        self,
        *,
        context: ProofCallDiagnosticContext,
        phase: str,
        exc: BaseException,
    ) -> Path | None:
        """Log an unexpected exception with traceback and return the log path."""
        entry = _base_entry(context, phase=phase, kind="exception")
        entry["exception"] = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": "".join(
                traceback.format_exception(type(exc), exc, exc.__traceback__)
            ),
        }
        return self._append(entry)

    def log_llm_error(
        self,
        *,
        context: ProofCallDiagnosticContext,
        phase: str,
        error: str,
        attempt: int | None = None,
    ) -> Path | None:
        """Log an LLM-call failure as surfaced by the loop (rate limit, timeout, …)."""
        entry = _base_entry(context, phase=phase, kind="llm_error")
        details: dict[str, Any] = {"message": str(error)}
        status_code = _status_code_of(error)
        if status_code is not None:
            details["status_code"] = status_code
        if attempt is not None:
            details["attempts"] = attempt
        entry["error"] = details
        return self._append(entry)

    def _append(self, entry: dict[str, Any]) -> Path | None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as file:
                file.write(json.dumps(entry, sort_keys=True, default=str) + "\n")
            return self.path
        except OSError:
            # Diagnostics must never break the proof loop.
            return None


def new_proof_call_run_id() -> str:
    """Return a stable id for one proof-session run (tau's new_agent_call_run_id)."""
    return uuid4().hex


def _base_entry(
    context: ProofCallDiagnosticContext,
    *,
    phase: str,
    kind: str,
) -> dict[str, Any]:
    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "kind": kind,
        "phase": phase,
        "run_id": context.run_id,
        "session_id": context.session_id,
        "problem_id": context.problem_id,
        "model": context.model,
        "cwd": str(context.cwd),
    }


def _status_code_of(error: str) -> int | None:
    """Pull an HTTP status code out of an error message when one is visible."""
    for token in ("429", "400", "401", "403", "404", "408", "409", "500", "502", "503", "504"):
        if token in error:
            return int(token)
    return None
