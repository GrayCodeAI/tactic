"""Unit tests for the Lean-verified data generation (agent/datagen.py)."""

from __future__ import annotations

import json
from pathlib import Path

from agent import datagen


def _write_corpus(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")


def _write_report(path: Path, tactic: str, solved_ids: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "tactic": tactic,
        "search_budget": 4000 if tactic == "prover_search" else None,
        "search_depth": 4 if tactic == "prover_search" else None,
        "solved_ids": solved_ids,
    }
    path.write_text(json.dumps(report), encoding="utf-8")


def test_gather_corpus_and_reports(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus" / "lean_proved.jsonl"
    _write_corpus(corpus, [
        {"id": "tpl_a", "difficulty": "templated",
         "statement": "theorem a := by trivial", "tactic": "prover_finish"},
        {"id": "auto_b", "difficulty": "auto",
         "statement": "theorem b := by simp", "tactic": "simp"},
    ])
    rep = tmp_path / "benchmark" / "lean_baseline_search.json"
    _write_report(rep, "prover_search", [
        {"id": "rep_c", "statement": "theorem c := by ring"},
    ])
    entries = datagen.gather(corpus, [rep])
    ids = {e["id"]: e for e in entries}
    assert set(ids) == {"tpl_a", "auto_b", "rep_c"}
    assert ids["tpl_a"]["fidelity"] == "templated"
    assert ids["auto_b"]["fidelity"] == "auto"
    assert ids["rep_c"]["fidelity"] == "native"
    assert ids["rep_c"]["tactic"] == "set_option prover_search.budget 4000\nprover_search 4"


def test_gather_dedupes_by_id(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus" / "lean_proved.jsonl"
    _write_corpus(corpus, [
        {"id": "dup", "difficulty": "templated",
         "statement": "theorem x := by exact?", "tactic": "exact?"},
    ])
    rep = tmp_path / "benchmark" / "report.json"
    _write_report(rep, "prover_finish", [{"id": "dup", "statement": "theorem x := by simp"}])
    entries = datagen.gather(corpus, [rep])
    assert len(entries) == 1


def test_gather_skips_missing_corpus(tmp_path: Path) -> None:
    entries = datagen.gather(tmp_path / "missing.jsonl", [])
    assert entries == []


def test_write_sft_shape(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus" / "lean_proved.jsonl"
    _write_corpus(corpus, [
        {"id": "loc", "difficulty": "auto",
         "statement": "theorem p : True := by trivial", "tactic": "trivial"},
    ])
    entries = datagen.gather(corpus, [])
    out = tmp_path / "train_sft.jsonl"
    n = datagen.write_sft(entries, out)
    assert n == 1
    rec = json.loads(out.read_text(encoding="utf-8"))
    assert rec["instruction"] == "theorem p : True"
    assert rec["output"].startswith("```lean")
    assert rec["fidelity"] == "auto"


def test_main_end_to_end(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus" / "lean_proved.jsonl"
    _write_corpus(corpus, [
        {"id": "x1", "difficulty": "auto",
         "statement": "theorem x1 : True := by trivial", "tactic": "trivial"},
    ])
    out = tmp_path / "sft.jsonl"
    rc = datagen.main(["--corpus", str(corpus), "--out", str(out)])
    assert rc == 0
    assert out.exists()
