import Mathlib

open BigOperators Nat Finset

/-! # ProverSupport

Lean-native proof search for the agent.

`prover_finish` runs the hammer chain *inside* a single Lean invocation —
`simp`, `ring`, `omega`, `linarith`, `nlinarith`, `norm_num`, `decide`,
`tauto`, `aesop`, `positivity` — trying each tactic until all goals are
closed. Tactic names are parsed at run time (via `runParserCategory`) so
macros like `tauto`/`aesop` expand only when actually executed, never at
quotation time.

The agent previously drove this chain from Python by spawning `lake env lean`
once per hammer (~10 compiles per problem); `prover_finish` does the same
search in one compile, entirely inside Lean.
-/

namespace ProverSupport

open Lean Elab Tactic

/-- The hammer chain, in order of preference. -/
def hammerNames : List String :=
  ["simp", "ring", "omega", "linarith", "nlinarith", "norm_num",
   "decide", "tauto", "aesop", "positivity"]

/-- Try one hammer; goals are untouched when it fails or is unknown. -/
def tryHammer (name : String) : TacticM Unit := do
  let stx := Lean.Parser.runParserCategory (← getEnv) `tactic name
  match stx with
  | .ok s => try evalTactic s catch _ => pure ()
  | .error _ => pure ()

/-- Run the hammer chain until all goals are closed (or the chain is spent). -/
elab "prover_finish" : tactic => do
  for name in hammerNames do
    let goals ← getGoals
    if goals.isEmpty then
      return
    tryHammer name
    let goals' ← getGoals
    if goals'.isEmpty then
      return

end ProverSupport
