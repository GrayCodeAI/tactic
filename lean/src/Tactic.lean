/-
  Target file: the agent rewrites this each step.
  Rule: keep the theorem statement, replace the proof. No `sorry` in a proved run.
-/

-- Starter theorem (true, easy). Replace via `tactic prove "..."`.
theorem sq_nonneg (x : ℤ) : 0 ≤ x ^ 2 := by
  sorry
