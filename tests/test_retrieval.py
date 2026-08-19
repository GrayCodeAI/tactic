"""Unit tests for the local Mathlib retrieval index (agent/retrieval.py).

The index is exercised against tiny synthetic "Mathlib" trees so tests stay
offline and fast; scoring/ranking and cache invalidation are the focus.
"""

from __future__ import annotations

from pathlib import Path

from agent import retrieval


def write_mathlib(lean_dir: Path, files: dict[str, str]) -> None:
    src = lean_dir / ".lake" / "packages" / "mathlib" / "Mathlib"
    for rel, text in files.items():
        f = src / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")


PRIME = """import Mathlib

theorem prime_mul_iff {a b : ℕ} : Nat.Prime (a * b) ↔ a.Prime ∧ b = 1 ∨ b.Prime ∧ a = 1 := by
  sorry

lemma prime_dvd_mul_iff {p a b : ℕ} : p.Prime → p ∣ a * b → p ∣ a ∨ p ∣ b := by
  sorry

theorem Nat.Prime.isPrimePow {p : ℕ} (hp : p.Prime) : IsPrimePow p := by
  sorry
"""

GCD = """import Mathlib

theorem gcd_mul_lcm (a b : ℕ) : Nat.gcd a b * Nat.lcm a b = a * b := by
  sorry

def SomeDef (x : ℕ) : ℕ where
  toFun := x
"""

FIB = """import Mathlib

theorem fib_add (m n : ℕ) : Nat.fib (m + n + 1) = Nat.fib m * Nat.fib n + Nat.fib (m + 1) * Nat.fib (n + 1) := by
  sorry
"""

FILES = {"Data/Nat/Prime/Basic.lean": PRIME, "Data/Nat/GCD.lean": GCD, "Data/Nat/Fib.lean": FIB}


def test_build_index_extracts_decls(tmp_path: Path) -> None:
    write_mathlib(tmp_path, FILES)
    idx = retrieval.build_index(tmp_path)
    names = {e["name"] for e in idx}
    assert {"prime_mul_iff", "prime_dvd_mul_iff", "gcd_mul_lcm", "fib_add", "Nat.Prime.isPrimePow"} <= names
    # `def ... where` bodies are not lemmas — skipped
    assert "SomeDef" not in names


def test_build_index_skips_import_lines_in_signature(tmp_path: Path) -> None:
    write_mathlib(tmp_path, FILES)
    idx = retrieval.build_index(tmp_path)
    fib = next(e for e in idx if e["name"] == "fib_add")
    assert ":= by" not in fib["signature"]
    assert "Nat.fib (m + n + 1) = Nat.fib m * Nat.fib n" in fib["signature"]


def test_search_ranks_relevant_lemma_first(tmp_path: Path) -> None:
    write_mathlib(tmp_path, FILES)
    idx = retrieval.build_index(tmp_path)
    stmt = "theorem prover_x (p a b : ℕ) : Nat.Prime p → p ∣ a * b → p ∣ a ∨ p ∣ b"
    hits = retrieval.search_lemmas(stmt, k=3, lean_dir=tmp_path, index=idx)
    assert hits, "expected at least one hit"
    assert hits[0]["name"] == "prime_dvd_mul_iff"


def test_search_respects_k(tmp_path: Path) -> None:
    write_mathlib(tmp_path, FILES)
    idx = retrieval.build_index(tmp_path)
    hits = retrieval.search_lemmas("Nat.fib m * Nat.fib n + Nat.fib (m + 1)", k=1, index=idx)
    assert len(hits) == 1
    assert hits[0]["name"] == "fib_add"


def test_search_returns_empty_for_unrelated_statement(tmp_path: Path) -> None:
    write_mathlib(tmp_path, FILES)
    idx = retrieval.build_index(tmp_path)
    hits = retrieval.search_lemmas("theorem xyz (q : Prop) : q → q", index=idx)
    assert hits == []


def test_cache_rebuilt_on_version_or_tree_change(tmp_path: Path, monkeypatch) -> None:
    write_mathlib(tmp_path, FILES)
    idx = retrieval.load_index(tmp_path)
    assert len(idx) == 5
    cache = tmp_path / "tmp" / "lemma_index.json"
    assert cache.exists()
    # tree change (new file) invalidates the cache
    write_mathlib(tmp_path, {"Data/Nat/Extra.lean": "theorem extra (n : ℕ) : n = n := by rfl\n"})
    idx2 = retrieval.load_index(tmp_path)
    assert {e["name"] for e in idx2} == {"prime_mul_iff", "prime_dvd_mul_iff", "gcd_mul_lcm", "fib_add", "Nat.Prime.isPrimePow", "extra"}
    # version bump forces a rebuild even without a tree change
    monkeypatch.setattr(retrieval, "CACHE_VERSION", 999)
    idx3 = retrieval.load_index(tmp_path)
    assert {e["name"] for e in idx3} == {e["name"] for e in idx2}


def test_enabled_flag(monkeypatch) -> None:
    assert retrieval.enabled() is False
    monkeypatch.setenv("PROVER_RETRIEVE", "1")
    assert retrieval.enabled() is True


def test_load_index_recovers_from_corrupt_cache(tmp_path: Path) -> None:
    write_mathlib(tmp_path, FILES)
    cache = tmp_path / "tmp" / "lemma_index.json"
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text("{{{ not json", encoding="utf-8")
    idx = retrieval.load_index(tmp_path)
    assert len(idx) == 5
