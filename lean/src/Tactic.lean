import Mathlib

open BigOperators Nat Finset

theorem tactic_not_not_self_eq (a : ℕ) : ¬¬(a = a) := by
  intro h
  apply h
  rfl
