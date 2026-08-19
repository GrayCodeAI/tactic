import Mathlib
import ProverSupport

open BigOperators Nat Finset

theorem arith (n : ℕ) : 2 * (∑ i in Finset.range (n + 1), i) = n * (n + 1) := by
  sorry
