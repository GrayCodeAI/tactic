"""Durable proof sessions — JSONL log per run under ~/.prover/sessions/.

A session records the full event stream of one `prove()` call plus the final
Result summary. Sessions let you inspect, resume-ish, and diff proof attempts
after the process exits.

Override the dir with PROVER_SESSIONS_DIR (handy for tests and CI).
Set PROVER_NO_SESSIONS=1 to disable recording entirely.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path


def _default_dir() -> Path:
    from ..paths import ProverPaths

    return ProverPaths().sessions_dir


def sessions_dir() -> Path:
    return _default_dir()


def _sanitize(text: str, fallback: str = "proof") -> str:
    slug = re.sub(r"\W+", "_", text)[:40].strip("_")
    return slug or fallback


class Session:
    """One JSONL file for one proof attempt."""

    def __init__(self, problem_id: str | None = None, enabled: bool = True) -> None:
        self._fh = None
        self.path: Path | None = None
        self.id = self._new_id(problem_id)

    @staticmethod
    def _new_id(problem_id: str | None) -> str:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        suffix = _sanitize(problem_id or "")
        return f"{stamp}-{suffix}" if suffix else stamp

    def open(self) -> bool:
        """Prepare the session file. Returns False if recording is off."""
        if os.environ.get("PROVER_NO_SESSIONS") == "1":
            return False
        d = sessions_dir()
        d.mkdir(parents=True, exist_ok=True)
        self.path = d / f"{self.id}.jsonl"
        self._fh = self.path.open("w", encoding="utf-8")
        return True

    def write(self, rec: dict) -> None:
        if self._fh is None:
            return
        try:
            self._fh.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
            self._fh.flush()
        except (OSError, TypeError):
            pass

    def close(self) -> None:
        if self._fh is not None:
            try:
                self._fh.close()
            finally:
                self._fh = None


def read_session(path: Path) -> list[dict]:
    """Read back all records from a session file."""
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def list_sessions() -> list[Path]:
    d = sessions_dir()
    if not d.exists():
        return []
    return sorted(d.glob("*.jsonl"), reverse=True)
