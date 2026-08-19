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


def test_source_of_categories():
    assert lb._source_of("minif2f_amc12_2001_p2") == "amc12"
    assert lb._source_of("minif2f_mathd_algebra_214") == "mathd"
    assert lb._source_of("minif2f_imo_2000_p1") == "imo"
    assert lb._source_of("plain_problem_x") == "plain"


def test_breakdown_counts_by_source():
    report = {
        "solved_ids": [{"id": "minif2f_mathd_algebra_1"}, {"id": "minif2f_imo_2000_p1"}],
        "unsolved_ids": [{"id": "minif2f_mathd_numbertheory_2"}],
    }
    by_source: dict[str, dict[str, list[str]]] = {}
    for s in report["solved_ids"] + report["unsolved_ids"]:
        key = lb._source_of(s["id"])
        bucket = by_source.setdefault(key, {"solved": [], "unsolved": []})
        which = "solved" if any(s["id"] == x["id"] for x in report["solved_ids"]) else "unsolved"
        bucket[which].append(s["id"])
    assert by_source["mathd"]["solved"] == ["minif2f_mathd_algebra_1"]
    assert by_source["mathd"]["unsolved"] == ["minif2f_mathd_numbertheory_2"]
    assert by_source["imo"]["solved"] == ["minif2f_imo_2000_p1"]


def test_report_only_mode(tmp_path: Path, capsys, monkeypatch):
    report = {
        "tactic": "prover_search",
        "total": 2,
        "solved": 1,
        "seconds": 10.0,
        "tiers": {"minif2f_valid": {"solved": 1, "total": 2}},
        "solved_ids": [{"id": "minif2f_imo_2000_p1", "difficulty": "minif2f_valid"}],
        "unsolved_ids": [{"id": "minif2f_mathd_algebra_214", "difficulty": "minif2f_valid"}],
    }
    f = tmp_path / "r.json"
    f.write_text(__import__("json").dumps(report), encoding="utf-8")
    assert lb.main(["--report-only", str(f)]) == 0
    out = capsys.readouterr().out
    assert "prover_search" in out and "1/2" in out
    assert "imo" in out and "mathd" in out
