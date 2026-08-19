"""`prover usage` CLI + proof-loop diagnostic-log wiring tests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from agent import main


def _write_usage_session(dir_path: Path, name: str, steps: int = 2) -> Path:
    recs = [{"t": 0, "event": "start", "problem_id": name, "statement": "t",
             "max_steps": 20, "model": "gpt-4o"}]
    for i in range(1, steps + 1):
        recs.append({"t": i, "event": "llm_request", "step": i})
        recs.append({"t": i, "event": "llm_response", "step": i,
                     "prompt_tokens": 100, "completion_tokens": 50,
                     "tokens": 150, "body": f"  body {i}"})
    sp = dir_path / f"{name}.jsonl"
    sp.write_text("\n".join(json.dumps(r) for r in recs) + "\n")
    return sp


def _ns(**kw) -> argparse.Namespace:
    return argparse.Namespace(**kw)


def test_no_args_launches_tui(monkeypatch) -> None:
    calls: list[object] = []

    def fake_tui(args: argparse.Namespace) -> int:
        calls.append(args)
        return 0

    monkeypatch.setattr(main, "cmd_tui", fake_tui)
    assert main.cli([]) == 0
    assert len(calls) == 1
    assert calls[0].parallel == 1


def test_tui_parallel_flag_reaches_cmd_tui(monkeypatch) -> None:
    calls: list[object] = []

    def fake_tui(args: argparse.Namespace) -> int:
        calls.append(args)
        return 0

    monkeypatch.setattr(main, "cmd_tui", fake_tui)
    with pytest.raises(SystemExit) as exc:
        main.cli(["tui", "-p", "3"])
    assert exc.value.code == 0
    assert calls[0].parallel == 3


def test_usage_cli_single_session(monkeypatch, tmp_path, capsys) -> None:
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    _write_usage_session(sessions, "sess-a")
    monkeypatch.setenv("PROVER_SESSIONS_DIR", str(sessions))
    rc = main.cmd_usage(_ns(id="sess-a"))
    out = capsys.readouterr().out
    assert rc == 0
    assert "Usage for sess-a" in out
    assert "Total tokens" in out


def test_usage_cli_all_sessions(monkeypatch, tmp_path, capsys) -> None:
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    _write_usage_session(sessions, "sess-a")
    _write_usage_session(sessions, "sess-b")
    monkeypatch.setenv("PROVER_SESSIONS_DIR", str(sessions))
    rc = main.cmd_usage(_ns(id=None))
    out = capsys.readouterr().out
    assert rc == 0
    assert "across 2 session" in out


def test_usage_cli_missing_session(monkeypatch, tmp_path, capsys) -> None:
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    _write_usage_session(sessions, "sess-a")
    monkeypatch.setenv("PROVER_SESSIONS_DIR", str(sessions))
    rc = main.cmd_usage(_ns(id="nope"))
    assert rc == 1
    assert "session not found" in capsys.readouterr().out
