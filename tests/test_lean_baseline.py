"""Unit tests for the Lean-native baseline runner (agent/lean_baseline.py)."""

from __future__ import annotations

from pathlib import Path

from agent import lean_baseline as lb


def test_build_lean_file_strips_sorry():
    text = lb.build_lean_file(
        "theorem foo (a b : \u2115) : a + b = b + a := by\n  sorry"
    )
    assert "import ProverSupport" in text
    assert "prover_finish" in text
    assert "sorry" not in text
    assert text.rstrip().endswith("prover_finish")


def test_build_lean_file_appends_by_when_missing():
    text = lb.build_lean_file("theorem foo (n : \u2115) : n + 0 = n")
    assert ":= by\n  prover_finish" in text


def test_load_problems_flat_list(tmp_path: Path):
    f = tmp_path / "p.json"
    f.write_text(
        '[{"id":"a","difficulty":"trivial","statement":"theorem a : True := by sorry"}]',
        encoding="utf-8",
    )
    ps = lb.load_problems(f)
    assert len(ps) == 1
    assert ps[0].id == "a"
    assert ps[0].difficulty == "trivial"


def test_load_problems_wrapped_dict(tmp_path: Path):
    f = tmp_path / "p.json"
    f.write_text(
        '{"problems": [{"id":"b","tier":"easy","statement":"theorem b : True := by sorry"}]}',
        encoding="utf-8",
    )
    ps = lb.load_problems(f)
    assert ps[0].id == "b"
    assert ps[0].difficulty == "easy"


def test_run_baseline_aggregates_and_tiers(tmp_path: Path, monkeypatch):
    probs = [
        lb.Problem("ok1", "trivial", "theorem ok1 : True := by sorry"),
        lb.Problem("bad1", "hard", "theorem bad1 : False := by sorry"),
        lb.Problem("ok2", "easy", "theorem ok2 : True := by sorry"),
    ]
    calls: list[str] = []

    def fake_check(f, lean_dir, timeout=120):
        calls.append(f.name)
        ok = f.name.startswith("Baseline_ok")
        return ok, ("" if ok else "unsolved goals")

    monkeypatch.setattr(lb, "check_file", fake_check)
    report = lb.run_baseline(probs, tmp_path, tmp_path, timeout=5)
    assert report["total"] == 3
    assert report["solved"] == 2
    assert len(calls) == 3
    assert report["tiers"]["trivial"] == {"solved": 1, "total": 1}
    assert report["tiers"]["hard"] == {"solved": 0, "total": 1}
    assert [s["id"] for s in report["solved_ids"]] == ["ok1", "ok2"]
    assert [s["id"] for s in report["unsolved_ids"]] == ["bad1"]


def test_build_lean_file_custom_tactic():
    text = lb.build_lean_file("theorem foo (n : \u2115) : n + 0 = n", "prover_search")
    assert text.rstrip().endswith("prover_search")


def test_build_lean_file_search_mode_sets_max_heartbeats():
    text = lb.build_lean_file("theorem foo (n : \u2115) : n + 0 = n", "prover_search")
    assert "set_option maxHeartbeats 0" in text
    plain = lb.build_lean_file("theorem foo (n : \u2115) : n + 0 = n")
    assert "maxHeartbeats" not in plain
