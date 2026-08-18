# Results post — drafts (X / HN / Lean Zulip)

Final: score 68/100 · flips dvd_sub_int, gcd_mul_right · wall ~7h first run
(02:30–09:36 UTC, 4 workers) + ~5.3h retry pass, $0 total.

## X (short, 280 chars)

```
Built an open-source agent that writes Lean 4 proofs: LLM draft → lake
compile → feed exact errors back → patch. 68/100 on my graded benchmark
with a 27B free Qwen endpoint. $0. Hammer pre-pass alone nukes the trivial
tier. Loop > clever prompting. github.com/GrayCodeAI/lean-prover
```

## Hacker News (Show HN)

Title: Show HN: Prover – An agent that writes Lean 4 proofs with a
compiler-error repair loop

Body:

Prover is a proof-writing agent for Lean 4. Give it a theorem statement
and it loops: the LLM drafts a proof → `lake build` type-checks it → the
exact compiler diagnostics + open goal state (via Lean LSP
`getInteractiveGoals`) go back to the model → it patches. Lean's errors
are machine-readable and precise, so generation turns into a convergent
repair loop instead of generate-and-hope. Nothing counts until the kernel
accepts it.

Result: 68/100 on a 100-problem graded benchmark (trivial 20/20, easy
23/30, medium 21/30, hard 4/20) using Qwen3.8-27B on a free HuggingFace
endpoint. Total cost: $0; ~2.3M tokens for the full run.

What worked:
- Hammer pre-pass: before spending any LLM tokens, try `ring`, `omega`,
  `linarith`, `nlinarith`, `simp`, `norm_num`, `decide`, `aesop`,
  `tauto`, `positivity`. This alone takes trivial from 15/20 to 20/20.
  ~3s each (one `lean --check` per hammer), most problems never reach
  the LLM.
- Goal-state feedback beats error-only feedback: showing the actual open
  goals (hypotheses + target), not just "2 diagnostics", measurably
  improved convergence.
- Per-problem file isolation → safe `--parallel 4`.
- History compaction: instead of truncating to the last N messages, fold
  old attempts into a summary of what already failed, so weak models stop
  re-trying the same dead ends.

What didn't: the same model re-fails the same problems. Re-running the 34
failures flipped 2 (medium tier). Score ceiling is model-bound; the
loop is not the bottleneck.

The repo also has: 100-problem benchmark in JSON, JSONL session logs,
session resume/branching (`/branch <session> <turn>`), an interactive
Textual TUI with live proof trace and replay, and an MCP server so any
agent can `prove_theorem`.

Looking for feedback on the benchmark design (Mathlib v4.20.0 pinned) and
on what people would trust as a public leaderboard.

## Lean Zulip (leanprover-community, topic in "General Mathlib")

Subject: proof-writing agent with error-repair loop — 68/100 on a graded
benchmark with a 27B model

Body (shorter, more technical than HN):

I built lean-prover, an agent that writes Lean 4 proofs against a pinned
Mathlib v4.20 project. The loop is: statement locked by us (the model only
writes the proof body), `lake env lean --check` per step, compiler
diagnostics with surrounding source context, plus open goal state via the
Lean LSP's `getInteractiveGoals` RPC. A prover hammer pre-pass
(ring/omega/linarith/… before any LLM call) solves a surprising number
outright.

Graded benchmark (100 problems): trivial 20/20, easy 23/30, medium 21/30,
hard 4/20 — 68/100 total, with Qwen3.8-27B on a free HF endpoint. Cost $0
(~2.3M tokens). Interesting: retries of the 34 failures flip very few —
the loop converges or it doesn't.

I'd especially like feedback on:
1. Benchmark composition (currently theorem statements about ℕ/ℤ/∑, some
   with Mathlib lemmas; anything I'm mismeasuring?)
2. What a minimal public leaderboard would need to be credible
   (statement hashing, sealed evaluation?)

Code + sessions: github.com/GrayCodeAI/lean-prover
