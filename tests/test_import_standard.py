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


# --------------------------------------------------------------- PutnamBench

PUTNAM_PLAIN = """import Mathlib

/-- A docstring. -/
theorem putnam_1962_a1 : 1 + 1 = 2 :=
sorry
"""

PUTNAM_SCAFFOLD = """import Mathlib

open MeasureTheory Set

abbrev putnam_1962_a2_solution : Set (ℝ → ℝ) := sorry
-- the comment answer

/-- Find every real-valued function ... -/
theorem putnam_1962_a2
    (P : Prop) :
    P :=
  sorry
"""

PUTNAM_MULTILINE_DOC = """import Mathlib

/--
multi-line
docstring -/
theorem putnam_1988_b6 : True :=
sorry
"""


def test_parse_putnam_plain(tmp_path: Path) -> None:
    f = write_problem(tmp_path, "putnam_1962_a1.lean", PUTNAM_PLAIN)
    p = im.parse_putnam_file(f)
    assert p["id"] == "putnam_1962_a1"
    assert p["difficulty"] == "putnam_1962"
    assert p["source"] == "putnambench"
    assert p["statement"] == "theorem prover_putnam_1962_a1 : 1 + 1 = 2 := by\n  sorry"
    assert "docstring" not in p["statement"]
    assert "import" not in p["statement"]


def test_parse_putnam_keeps_scaffold_and_opens(tmp_path: Path) -> None:
    f = write_problem(tmp_path, "putnam_1962_a2.lean", PUTNAM_SCAFFOLD)
    p = im.parse_putnam_file(f)
    assert p["statement"].startswith("open MeasureTheory Set\n")
    assert "abbrev putnam_1962_a2_solution : Set (ℝ → ℝ) := sorry" in p["statement"]
    assert "comment answer" not in p["statement"]
    assert p["statement"].endswith("theorem prover_putnam_1962_a2\n    (P : Prop) :\n    P := by\n  sorry")


def test_parse_putnam_drops_multiline_docstring(tmp_path: Path) -> None:
    f = write_problem(tmp_path, "putnam_1988_b6.lean", PUTNAM_MULTILINE_DOC)
    p = im.parse_putnam_file(f)
    assert "multi-line" not in p["statement"]
    assert p["statement"] == "theorem prover_putnam_1988_b6 : True := by\n  sorry"


def test_parse_putnam_rejects_bad_name(tmp_path: Path) -> None:
    f = write_problem(tmp_path, "p.lean", "import Mathlib\n\ntheorem not_putnam : True := sorry\n")
    with pytest.raises(ValueError, match="unexpected theorem name"):
        im.parse_putnam_file(f)


def test_parse_putnam_rejects_two_theorems(tmp_path: Path) -> None:
    f = write_problem(tmp_path, "p.lean", "theorem putnam_1962_a1 : True := sorry\ntheorem putnam_1962_a2 : True := sorry\n")
    with pytest.raises(ValueError, match="exactly one theorem"):
        im.parse_putnam_file(f)


def test_parse_putnam_rejects_decl_before_theorem(tmp_path: Path) -> None:
    f = write_problem(tmp_path, "p.lean", "lemma hidden : True := by sorry\ntheorem putnam_1962_a1 : True := sorry\n")
    with pytest.raises(ValueError, match="unexpected declaration"):
        im.parse_putnam_file(f)


def test_import_putnam_collects_and_sorts(tmp_path: Path) -> None:
    write_problem(tmp_path, "lean4/src/putnam_1963_b1.lean", PUTNAM_PLAIN.replace("putnam_1962_a1", "putnam_1963_b1"))
    write_problem(tmp_path, "lean4/src/putnam_1962_a1.lean", PUTNAM_PLAIN)
    write_problem(tmp_path, "lean4/src/other.lean", "def x := 1\n")  # skipped
    problems = im.import_putnam(tmp_path)
    assert [p["id"] for p in problems] == ["putnam_1962_a1", "putnam_1963_b1"]
    assert problems[0]["difficulty"] == "putnam_1962"
    assert problems[1]["difficulty"] == "putnam_1963"


def test_import_putnam_limit_and_errors(tmp_path: Path) -> None:
    for name in ("putnam_1962_a1", "putnam_1962_a2", "putnam_1963_b1"):
        write_problem(tmp_path, f"lean4/src/{name}.lean", PUTNAM_PLAIN.replace("putnam_1962_a1", name))
    assert len(im.import_putnam(tmp_path, limit=2)) == 2
    with pytest.raises(FileNotFoundError, match="lean4/src"):
        im.import_putnam(tmp_path / "nope")
    empty = tmp_path / "empty"
    (empty / "lean4" / "src").mkdir(parents=True)
    with pytest.raises(FileNotFoundError, match=r"no putnam_\*\.lean"):
        im.import_putnam(empty)


# ------------------------------------------------------------ FormalQualBench

FQ_SAMPLE = """import Mathlib
import Mathlib.Data.Nat.Prime.Basic

namespace TernaryGoldbachTheorem

/-- Helfgott's ternary Goldbach theorem. -/
theorem MainTheorem :
    ∀ n : ℕ,
      n % 2 = 1 →
        5 < n → ∃ p q r : ℕ, p.Prime ∧ q.Prime ∧ r.Prime ∧ n = p + q + r := by
  sorry

end TernaryGoldbachTheorem
"""

FQ_WITH_DEFS = """import Mathlib

namespace CollatzMapAlmostBoundedValues

/-- Collatz map. -/
def collatz (n : ℕ) : ℕ :=
  if Even n then n / 2 else 3 * n + 1

theorem MainTheorem :
    True := by
  sorry

end CollatzMapAlmostBoundedValues
"""


def test_parse_formalqual(tmp_path: Path) -> None:
    f = write_problem(tmp_path, "TernaryGoldbachTheorem/Main.lean", FQ_SAMPLE)
    p = im.parse_formalqual_file(f)
    assert p["id"] == "formalqual_TernaryGoldbachTheorem"
    assert p["difficulty"] == "formalqual"
    assert p["source"] == "formalqualbench"
    assert p["source_name"] == "TernaryGoldbachTheorem"
    assert "import " not in p["statement"]
    assert p["statement"].startswith("namespace TernaryGoldbachTheorem\n")
    assert "theorem prover_MainTheorem :" in p["statement"]
    assert "theorem MainTheorem :" not in p["statement"]
    assert p["statement"].endswith(" := by\n  sorry")


def test_parse_formalqual_keeps_scaffolding_defs(tmp_path: Path) -> None:
    f = write_problem(tmp_path, "CollatzMapAlmostBoundedValues/Main.lean", FQ_WITH_DEFS)
    p = im.parse_formalqual_file(f)
    assert "def collatz" in p["statement"]
    assert "namespace CollatzMapAlmostBoundedValues" in p["statement"]
    assert "end CollatzMapAlmostBoundedValues" not in p["statement"]
    # the theorem is the last declaration; only the final `:= by` gets the
    # canonical sorry appended by consumers splitting at the last `:= by`
    assert p["statement"].count("prover_MainTheorem") == 1


def test_parse_formalqual_rejects_missing_theorem(tmp_path: Path) -> None:
    f = write_problem(tmp_path, "X/Main.lean", "def x := 1\n")
    with pytest.raises(ValueError, match="exactly one MainTheorem"):
        im.parse_formalqual_file(f)


def test_import_formalqual_collects_and_sorts(tmp_path: Path) -> None:
    write_problem(tmp_path, "FormalQualBench/Zzz/Main.lean", FQ_SAMPLE.replace("TernaryGoldbachTheorem", "Zzz"))
    write_problem(tmp_path, "FormalQualBench/Aaa/Main.lean", FQ_SAMPLE.replace("TernaryGoldbachTheorem", "Aaa"))
    problems = im.import_formalqual(tmp_path)
    assert [p["id"] for p in problems] == ["formalqual_Aaa", "formalqual_Zzz"]


def test_import_formalqual_limit_and_errors(tmp_path: Path) -> None:
    for name in ("Aaa", "Bbb", "Ccc"):
        write_problem(tmp_path, f"FormalQualBench/{name}/Main.lean",
                      FQ_SAMPLE.replace("TernaryGoldbachTheorem", name))
    assert len(im.import_formalqual(tmp_path, limit=2)) == 2
    assert len(im.import_formalqual(tmp_path)) == 3
    with pytest.raises(FileNotFoundError, match="expected FormalQualBench directory"):
        im.import_formalqual(tmp_path / "nope")
    empty = tmp_path / "empty"
    (empty / "FormalQualBench").mkdir(parents=True)
    with pytest.raises(FileNotFoundError, match="no <Name>/Main.lean"):
        im.import_formalqual(empty)
