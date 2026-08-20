import Mathlib
import ProverSupport

open BigOperators Nat Finset

theorem prover_loop (n : ℕ) : n + 0 = n := by
  prover_finish
