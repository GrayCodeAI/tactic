# PROPOSALS-LEAN.md — Phase 2: Lean-native (use Lean as much as possible)

Goal: move every piece of proof *intelligence* into Lean, keeping Python only
for what Lean cannot do (LLM calls, sessions, CLI/TUI/MCP, process/HTTP).
Everything math-flavored should run inside `lean --server` / one `lake env lean`.

## Why the split exists (and where the line is)

| Layer | Owner | Why |
|---|---|---|
| Proof checking (kernel) | Lean | the only judge of correctness |
| Proof search (hammers, native search) | **Lean** ← moving here | `prover_finish` runs the 10-hammer chain in **1 compile** vs Python's 10 |
| Statement type-checking | Lean | `lake env lean` / `compile_only` |
| Goal-state capture | Lean LSP | `getInteractiveGoals` (already Lean) |
| Tactics / strategy | Lean metaprograms | new `ProverSupport` lib |
| LLM prompting / repair loop | Python | no Lean HTTP client; must stay |
| Sessions / resume / TUI / MCP / CLI | Python | systems tooling; must stay |

**Verified foundation (2026-08-19):** `lean/src/ProverSupport/ProverSupport.lean`
builds into an importable olean (`lake build ProverSupport`); `prover_finish`
solves add_comm, Even(2n), diff-of-squares, Odd→Odd+2 natively and correctly
leaves `Prime p → 2 ≤ p` open — identical coverage to the old Python hammer
pass, in one Lean compile.

---

## L1 — Integrate `prover_finish` as the hammer pre-pass  ✅ (tactic done; wiring next)
**Goal**: kill the Python 10×`lake env lean` pre-pass (~30 s/problem) and
replace it with one compile that runs the whole chain inside Lean.
**Scope**: 
- loop `HEADER` gains `import ProverSupport`.
- Hammer pre-pass becomes a single check of `signature + "\n  prover_finish"`.
  If it proves → done, zero LLM tokens. If not → proceed to LLM exactly as
  today (chain exhausted; `prover_finish` failure == all 10 hammers failed).
- Keep `--no-hammers` semantics (skip the single compile).
**Acceptance**: hammer-solves problems still solve with 1 compile; step count
in `result` unchanged (report as 1); `--no-hammers` still works.
**Verification**: ✅ Unit (mock check_file to return ok once) + ✅ Real (run a
few benchmark trivial/easy problems through the pre-pass on real Lean).
**Honest note**: the chain is *slightly stronger* than before (tactics compose
sequentially in one file), so the 68/100 baseline may rise slightly on
hammer-solvable problems — measure it (L7).

## L2 — Lean-native baseline runner (`prover lean-baseline`)
**Goal**: an honest number: "how many of the 100 (or 244 MiniF2F) problems
does Lean itself solve, no LLM at all?"
**Scope**: one Lean file per problem is overkill; instead a Python driver that,
for each problem, writes `import ProverSupport` + the statement + `prover_finish`
and runs `lake env lean` once. Output: per-tier solved counts.
**Acceptance**: produces solved/unsolved lists + tier table; runs on real Lean.
**Verification**: ✅ Real (full 100-problem run). This is the honest
before-LLM baseline that the leaderboard can grow from.

## L3 — Native bounded search tactic (`prover_search`)
**Goal**: Lean-internal search that the (blocked) `runTactic` RPC was going to
provide, done the Lean way: a metaprogram that does bounded goal
decomposition + backtracking.
**Scope**: in `ProverSupport`: `prover_search [depth]` =
`(first | prover_finish | cases * <;> prover_search (d-1) | induction … | simp_all; …)`
with a depth cap (default 3) and heartbeat guard. Deterministic, no LLM.
**Acceptance**: proves statements that need a case split / a simple induction
(e.g. `a ∣ b → a ∣ b*c`, `n < 2^n`) within a few seconds per theorem.
**Verification**: ✅ Real (unit-style `.lean` checks in `lean/tmp`).

## L4 — `prover_elab` statement canonicalization (optional, low value)
Check the formalized statement is *meaningful* before spending tokens: run
`simp`-normal-form comparison? **Decision: skip** — compile-only already
catches malformed statements; canonical-form checking is a research problem.

## L5 — Lean-native proof corpus (`prover synth-lean`)
**Goal**: training data generated *by Lean*, not by the LLM.
**Scope**: generate N theorem statements (from mathlib-flavored templates or
the benchmark), prove each with `prover_finish`/`prover_search` in Lean;
output JSONL of `(statement, "prover_finish")` pairs that Lean itself proved.
This is the "expert" half of expert iteration with zero model cost.
**Acceptance**: corpus contains only statements Lean proved; counts match.
**Verification**: ✅ Real (Lean closes every entry; Python just aggregates).

## L6 — Keep LSP goal feedback, add `prover_report` printing (optional)
**Decision: keep LSP** (`getInteractiveGoals` already works). A Lean-side
`logInfo`-based goal dumper adds nothing.

## L7 — Docs + honest baseline section
README/PROPOSALS-LEAN checkoff; record the L2 baseline and any change in the
68/100 after L1.

## Deferred / not possible in Lean (documented)
- LLM API calls, JSON-RPC transport, sessions, TUI, MCP server, CLI,
  parallel benchmark orchestration → Python (no Lean ecosystem).
- `runTactic` RPC → Lean ≥ v4.22; L3's `prover_search` is the v4.20-native
  replacement.
- Real RL fine-tune → external (GPU).

## Order & dependencies
L1 (wiring, done tactic) → L2 (baseline, needs L1) → L3 (native search,
extends ProverSupport) → L5 (synth-lean, needs L3) → L7 (docs) → double-verify.
Everything is additive; the Python loop's default behavior only changes where
Lean replaces Python work (strictly fewer compiles).
