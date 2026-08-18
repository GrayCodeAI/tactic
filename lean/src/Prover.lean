import Mathlib

open BigOperators Nat Finset

theorem prover_not_not_self_eq (a : ℕ) : ¬¬(a = a) := by
  omega
