import Mathlib

open BigOperators Nat Finset

theorem sq_nonneg' (x : ℤ) : 0 ≤ x ^ 2 := by
  exact sq_nonneg x
