import Mathlib
import ProverSupport

open BigOperators Nat Finset

theorem sq_odd (n : ℕ) (h : Odd n) : ∃ k : ℕ, n * n = 4 * k + 1 := by
  obtain ⟨m, rfl⟩ := h
  use m * (m + 1)
  ring
