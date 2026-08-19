"""Unit tests for synthetic data generation (agent/synth.py)."""

from __future__ import annotations

import json
from pathlib import Path

from agent import loop, synth


def _fake_prove(monkeypatch, outcomes: list[tuple[bool, int, str]]) -> None:
    i = {"n": 0}

    def fake(statement, **kwargs):
        idx = min(i["n"], len(outcomes) - 1)
        i["n"] += 1
        proved, steps, proof = outcomes[idx]
        return loop.Result(statement=statement, proved=proved, steps=steps,
                           seconds=0.5, total_tokens=100, estimated_cost_usd=0.001,
                           proof=proof, attempts=[1])

    monkeypatch.setattr(synth, "prove_best_of", fake)


def test_generate_writes_all_and_train_split(tmp_path: Path, monkeypatch) -> None:
    _fake_prove(monkeypatch, [(True, 2, "theorem a : True := by\n  trivial"),
                              (False, 5, "")])
    out = tmp_path / "data.jsonl"
    summary = synth.generate(["theorem a : True := by sorry",
                              "theorem b : False := by sorry"], str(out))
    assert summary["total"] == 2 and summary["proved"] == 1 and summary["exhausted"] == 1

    all_rows = [json.loads(l) for l in out.read_text().splitlines()]
    assert len(all_rows) == 2
    assert all_rows[0]["proved"] is True
    assert all_rows[1]["proved"] is False

    train_rows = [json.loads(l) for l in out.with_name("data_train.jsonl").read_text().splitlines()]
    assert len(train_rows) == 1
    assert train_rows[0]["proved"] is True
    assert "trivial" in train_rows[0]["proof"]
    assert all("statement" in r and "steps" in r and "tokens" in r for r in train_rows)


def test_generate_empty_proven_writes_empty_train(tmp_path: Path, monkeypatch) -> None:
    _fake_prove(monkeypatch, [(False, 3, "")])
    out = tmp_path / "d.jsonl"
    summary = synth.generate(["theorem x : False := by sorry"], str(out))
    assert summary["proved"] == 0
    assert out.with_name("d_train.jsonl").read_text() == ""


def test_main_with_seeds_file(tmp_path: Path, monkeypatch, capsys) -> None:
    _fake_prove(monkeypatch, [(True, 1, "theorem s : True := by\n  trivial")])
    seeds = tmp_path / "seeds.txt"
    seeds.write_text("theorem s : True := by sorry\n", encoding="utf-8")
    rc = synth.main(["--seeds", str(seeds), "--out", str(tmp_path / "m.jsonl")])
    assert rc == 0
    out_lines = capsys.readouterr().out
    assert "total=1 proved=1" in out_lines
    train = [json.loads(l) for l in (tmp_path / "m_train.jsonl").read_text().splitlines()]
    assert len(train) == 1


def test_main_no_seeds_returns_error(tmp_path: Path, monkeypatch) -> None:
    empty = tmp_path / "empty.jsonl"
    empty.write_text("[]", encoding="utf-8")
    rc = synth.main(["--problems", str(empty), "--count", "5", "--out", str(tmp_path / "n.jsonl")])
    assert rc == 1
