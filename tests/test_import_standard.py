"""Unit tests for the standard-benchmark importer (benchmark/import_standard.py).

Parsing is tested against synthetic MiniF2F-style files. The `--verify` pass
is tested with `lean.compile_only` mocked — no real Lake/Mathlib or network.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from benchmark import import_standard as im


def write_problem(root: Path, rel: str, body: str) -> Path:
    f = root / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(body, encoding="utf-8")
    return f


SAMPLE = """import Mathlib

set_option maxHeartbeats 0

open BigOperators Real Nat Topology Rat

theorem aime_1983_p1
  (x y z w : ℕ)
  (ht : 1 < x ∧ 1 < y ∧ 1 < z) :
  x + y + z = w := by
  sorry
"""


def test_parse_single_theorem(tmp_path: Path) -> None:
    f = write_problem(tmp_path, "p.lean", SAMPLE)
    p = im.parse_problem_file(f)
    assert p["id"] == "minif2f_aime_1983_p1"
    assert p["source_name"] == "aime_1983_p1"
    assert p["statement"].startswith("set_option maxHeartbeats 0\nopen BigOperators Real Nat Topology Rat\n")
    assert "theorem prover_aime_1983_p1" in p["statement"]
    assert "theorem aime_1983_p1" not in p["statement"]


def test_parse_renames_and_normalizes_sorry(tmp_path: Path) -> None:
    f = write_problem(tmp_path, "p.lean", SAMPLE)
    p = im.parse_problem_file(f)
    # source's `:= by\n  sorry` is normalized to the repo's canonical suffix
    assert p["statement"].endswith(" := by\n  sorry")
    assert ":= by\n  sorry" in p["statement"]


def test_parse_drops_imports_and_comments(tmp_path: Path) -> None:
    body = """-- a header comment
/- a block
comment -/
import Mathlib
import MiniF2F.Test.foo

set_option maxHeartbeats 0

open BigOperators Real Nat

theorem foo (a : ℕ) : a = a := by sorry
"""
    f = write_problem(tmp_path, "p.lean", body)
    p = im.parse_problem_file(f)
    assert "import " not in p["statement"]
    assert "comment" not in p["statement"]
    assert "set_option maxHeartbeats 0" in p["statement"]
    assert "open BigOperators Real Nat" in p["statement"]


def test_parse_rejects_zero_or_many_theorems(tmp_path: Path) -> None:
    f = write_problem(tmp_path, "zero.lean", "import Mathlib\n\ndef x := 1\n")
    with pytest.raises(ValueError, match="exactly one theorem"):
        im.parse_problem_file(f)
    f2 = write_problem(tmp_path, "two.lean", "import Mathlib\n\ntheorem a : True := by sorry\ntheorem b : False := by sorry\n")
    with pytest.raises(ValueError, match="exactly one theorem"):
        im.parse_problem_file(f2)


def test_import_minif2f_collects_and_sorts(tmp_path: Path) -> None:
    write_problem(tmp_path, "MiniF2F/Test/alpha.lean",
                  "import Mathlib\n\nset_option maxHeartbeats 0\n\nopen BigOperators Real Nat Topology Rat\n\ntheorem alpha (a : ℕ) : a = a := by sorry\n")
    write_problem(tmp_path, "MiniF2F/Test/beta.lean",
                  "import Mathlib\n\nset_option maxHeartbeats 0\n\nopen BigOperators Real Nat Topology Rat\n\ntheorem beta (a b : ℕ) : a + b = b + a := by sorry\n")
    problems = im.import_minif2f(tmp_path, "test")
    assert [p["id"] for p in problems] == ["minif2f_alpha", "minif2f_beta"]
    assert all(p["difficulty"] == "minif2f_test" for p in problems)
    assert all(p["source"] == "minif2f" for p in problems)


def test_import_minif2f_limit(tmp_path: Path) -> None:
    for name in "abcdefg":
        write_problem(tmp_path, f"MiniF2F/Test/{name}.lean",
                      f"import Mathlib\n\ntheorem {name} (a : ℕ) : a = a := by sorry\n")
    assert len(im.import_minif2f(tmp_path, "test", limit=3)) == 3
    assert len(im.import_minif2f(tmp_path, "test")) == 7


def test_import_minif2f_missing_split(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="expected split directory"):
        im.import_minif2f(tmp_path, "valid")


def test_verify_marks_compiling_and_flags_errors(tmp_path: Path, monkeypatch) -> None:
    problems = [
        {"id": "minif2f_good", "difficulty": "minif2f_test", "statement": "theorem prover_good : True := by\n  sorry"},
        {"id": "minif2f_bad", "difficulty": "minif2f_test", "statement": "theorem prover_bad : False := by\n  sorry"},
    ]
    written: list[str] = []

    def fake_compile_only(file: Path, _dir: Path, timeout: int = 60) -> tuple[int, str]:
        text = file.read_text()
        written.append(text)
        return (0, "") if "prover_good" in text else (1, "boom")

    monkeypatch.setattr(im.lean, "compile_only", fake_compile_only)
    monkeypatch.setattr(im.lean, "error_report", lambda _d, out, max_diags=8, context=4: f"REPORT({out})")

    checked = im.verify(problems, tmp_path, timeout=30)
    assert checked[0]["compiles"] is True and checked[0]["error"] == ""
    assert checked[1]["compiles"] is False
    assert "REPORT(boom)" in checked[1]["error"]
    # originals untouched
    assert "compiles" not in problems[0]
    # every file checked carries the agent header + statement, and is cleaned up
    assert len(written) == 2
    assert not list(tmp_path.glob("*.lean"))


def test_verify_header_prepended(tmp_path: Path, monkeypatch) -> None:
    problems = [{"id": "minif2f_x", "difficulty": "minif2f_test", "statement": "theorem prover_x : True := by\n  sorry"}]
    captured: list[str] = []

    def fake_compile_only(file: Path, _dir: Path, timeout: int = 60) -> tuple[int, str]:
        captured.append(file.read_text())
        return 0, ""

    monkeypatch.setattr(im.lean, "compile_only", fake_compile_only)
    im.verify(problems, tmp_path)
    assert captured[0].startswith("import Mathlib")
    assert "theorem prover_x : True := by" in captured[0]
