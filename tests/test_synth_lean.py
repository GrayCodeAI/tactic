"""Unit tests for the Lean-native corpus generator (agent/synth_lean.py)."""

from __future__ import annotations

import json
from pathlib import Path

from agent import synth_lean


def _report() -> dict:
    return {
        "tactic": "prover_finish",
        "total": 2,
        "solved": 2,
        "solved_ids": [
            {"id": "a", "difficulty": "trivial",
             "statement": "theorem a : True := by sorry"},
            {"id": "b", "difficulty": "easy",
             "statement": "theorem b (n : \u2115) : n + 0 = n := by sorry"},
        ],
        "unsolved_ids": [{"id": "c", "difficulty": "hard",
                          "statement": "theorem c : False := by sorry"}],
    }


def test_corpus_lines_only_solved():
    lines = synth_lean.corpus_lines(_report())
    assert len(lines) == 2
    assert all("c" != l["id"] for l in lines)
    assert all(l["tactic"] == "prover_finish" for l in lines)
    assert lines[1]["id"] == "b"


def test_write_corpus_jsonl(tmp_path: Path):
    out = tmp_path / "corpus.jsonl"
    n = synth_lean.write_corpus(_report(), out)
    assert n == 2
    entries = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines()]
    assert entries[0]["statement"].startswith("theorem a")
    assert {e["id"] for e in entries} == {"a", "b"}


def test_load_report_roundtrip(tmp_path: Path):
    f = tmp_path / "report.json"
    f.write_text(json.dumps(_report()), encoding="utf-8")
    assert synth_lean.load_report(f)["solved"] == 2
