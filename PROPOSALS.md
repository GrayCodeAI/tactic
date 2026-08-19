# PROPOSALS.md — Ladder to a credible math-AI agent

Plan to take lean-prover from a 68/100 hobby benchmark to a MiniF2F/PutnamBench-
comparable, retrieval-augmented, search-enabled prover. Each item is built on
code that already exists. Every item has a **verification level** so nobody
mistakes "implemented + unit-tested" for "verified against a real model/Lean run":

| Level | Meaning |
|---|---|
| ✅ Unit | Logic verified by tests (mocks for LLM/Lean). Fully offline. |
| ✅ Real | Verified against the real Lean toolchain (v4.20 installed locally). |
| 🔶 Model | Code complete; needs a live LLM endpoint to produce numbers. |
| 🔶 External | Needs external resource (API key, compute, community/PR). |

Baseline (established 2026-08-19): 302 tests green, `ruff` clean, Lean 4.20.0
toolchain present, network available.

## Status (2026-08-19)

All 9 items are landed (317 tests green, `ruff` clean). Honest per-item outcome:

| Item | Status | Verified |
|---|---|---|
| 1 Standard-benchmark import | ✅ DONE | ✅ Unit + ✅ Real — **all 244/244 MiniF2F `test` statements type-check on our pinned Mathlib v4.20.0** (artifact `benchmark/minif2f_test.json`). |
| 2 Best-of-N search | ✅ DONE | ✅ Unit (loop + tests). Model gain 🔶 blocked: endpoint hangs. |
| 3 Mathlib lemma retrieval | ✅ DONE | ✅ Unit + ✅ Real — index of 149,620 signatures built from the local mathlib tree; hit quality spot-checked. |
| 4 Model router | ✅ DONE | ✅ Unit (incl. loop-level routing). Model numbers 🔶 blocked. |
| 5 Autoformalization | ✅ DONE | ✅ Unit. Live model attempt 🔶 blocked: HF endpoint answers `/models` but hangs on `/chat/completions` (serverless stall). |
| 6 Lemma-bank planning | ✅ DONE | ✅ Unit (proven-helpers-only, never `sorry`). Model gain 🔶 blocked. |
| 7 Synthetic data | ✅ DONE | ✅ Unit. Fine-tuning itself remains External (GPU). |
| 8 LSP `runTactic` primitive | ✅ DONE | ✅ Unit + ✅ Real-failure: **the RPC `Lean.Widget.runTactic` does not exist in pinned Lean v4.20.0** (server: "No RPC method found"); primitive degrades to `None`, documented. Usable after toolchain bump. |
| 9 Docs | ✅ DONE | ✅ Unit-consistent (README env/commands match code). |

Blocked live-model verification is a single root cause: the configured HF
endpoint does not serve inference right now. Everything model-facing is
implemented + unit-tested, and explicitly NOT claimed as model-verified.

---

## Item 1 — Standard benchmark import (MiniF2F / PutnamBench)
**Goal**: comparable scores. `benchmark/problems.json` is hand-curated; nothing
we report is comparable to DeepSeek-Prover-V2 (~50% MiniF2F Lean4) or LeanDojo.
**Scope**: `benchmark/import_standard.py` — fetch a source (URL or local JSONL),
normalize to our `{id, difficulty, statement}` shape, dedupe, prefix theorem
names with `prover_` to avoid mathlib collisions, and optionally `lean --check`
a sample so statements are known-compilable. `prover bench --problems` then
runs it unchanged.
**Acceptance**: import of a small real sample yields valid JSON + statements
that compile in Lean (`sorry`). Import fails loudly on bad/missing data.
**Verification level**: ✅ Unit + ✅ Real (sample compile).
**Honest note**: full MiniF2F is ~2400 statements; compiling/benchmarking all of
it needs model tokens + hours. We ship the tooling + a verified sample; the
full run is a Model-level follow-up.

---

## Item 2 — Best-of-N / beam search over attempts
**Goal**: inference-time search without any training (the cheapest RL).
**Scope**: `prove(..., n_attempts=N)`. Hammers run once; then N independent
LLM trajectories at spread temperatures; each writes its own session. Rank
attempts by a goal-state heuristic (fewest open goals / earlier `build ok`),
keep the best, keep the others for future resume. Wire `--n-attempts` into
`prover prove`/`bench`. Reuses existing `ThreadPoolExecutor`, sessions,
resume, compaction.
**Acceptance**: with `n_attempts=3`, a run the single-attempt path fails now
succeeds (mock: 2 of 3 trajectories solve) and the best result is returned.
**Verification level**: ✅ Unit. (Real-model gain must be measured with a live
endpoint — Model-level.)

---

## Item 3 — Mathlib lemma retrieval
**Goal**: the model currently proves from memory; mathlib has 210k+ theorems.
LeanDojo's retrieval is a ~10-point lever.
**Scope**: `agent/retrieval.py`. Build a local token index over the pinned
mathlib sources (`lean/.lake/packages/mathlib/Mathlib/**/*.lean`): extract
declaration names + first statement line, index tokens. `search_lemmas(stmt,
k)` → top-k by token overlap (bonus for namespace prefix). When enabled, inject
a `Available lemmas:` block into the loop prompt (`PROVER_RETRIEVE=1`).
No network at query time (index built once offline).
**Acceptance**: on a fake mathlib tree, retrieval returns the known-relevant
lemma; prompt gains the injected block; index build is idempotent.
**Verification level**: ✅ Unit + ✅ Real (index builds over the real mathlib
tree present locally).

---

## Item 4 — Model router
**Goal**: spend frontier tokens only where they matter (hard tier).
**Scope**: `agent/router.py`. Env table `PROVER_MODEL_TRIVIAL/EASY/MEDIUM/HARD`
(and per-tier temperature/max-steps), defaulting to `PROVER_MODEL`. `prove`
and `bench` pick model/params from the problem difficulty. Uses existing
`thinking.py` + cost tracking.
**Acceptance**: difficulty → (model, temperature, max_steps) mapping correct;
env overrides win; defaults unchanged when unset.
**Verification level**: ✅ Unit. (Real numbers need endpoints.)

---

## Item 5 — Autoformalization
**Goal**: input natural-language problems (olympiad / Erdős / user text), the
pipeline Prover-V2 and the 2026 Erdős solves use.
**Scope**: `agent/formalize.py`. NL → Lean `theorem … := by sorry` via LLM;
verify it compiles with `lean.check_file`; retry with diagnostics on failure.
`prover formalize "<NL problem>"` prints a formalized, compilable statement.
**Acceptance**: with a mock LLM that echoes a template, output compiles and the
retry-on-error path is exercised (tested with a fake lean layer).
**Verification level**: ✅ Unit + ✅ Real (formalized output compiles with Lean
4.20 — needs a real LLM only for the generation step, which is mockable).

---

## Item 6 — Lemma-bank planning
**Goal**: hard theorems fail because the model tries one monolithic proof.
ProofAgent's lesson: prove a bank of lemmas first, then chain.
**Scope**: `agent/plan.py`. For a hard statement: ask the model for ≤3 candidate
supporting lemmas; prove each with the existing loop; then prove the main
statement with the proven lemmas prepended to the file. Off by default
(`PROVER_LEMMA_PLAN=1`).
**Acceptance**: with mocks, lemmas are proven before the main theorem and their
declarations appear in the final file.
**Verification level**: ✅ Unit. (Real gain measured only with a live model.)

---

## Item 7 — Synthetic data + expert iteration (RLVR-lite)
**Goal**: turn successful runs into training signal.
**Scope**: `agent/synth.py`. Generate a corpus of statements (seeded from the
benchmark + mathlib-flavored patterns with `sorry`), run the loop over them,
emit `(statement, proof, ok, steps)` JSONL plus aggregate stats, and produce a
fine-tune-ready `train.jsonl` of successful proofs. `prover synth-data`.
**Acceptance**: pipeline runs with a mocked loop; output counts match inputs;
train.jsonl only contains proven examples.
**Verification level**: ✅ Unit. (Fine-tuning itself needs GPU/API — External.)

---

## Item 8 — LSP `runTactic` primitive
**Goal**: sub-second tactic-level feedback and backtracking (AlphaProof-style
step search) instead of ~3s whole-file recompiles.
**Scope**: extend `lsp.py` with `run_tactic(text, pos, tactic)` using Lean's
`Lean.Widget.runTactic` RPC → new goals; format results; test protocol layer.
Full interactive search loop is NOT rebuilt in this pass (architectural change,
needs real-LSP soak) — we land the primitive + tests.
**Acceptance**: `run_tactic` request serializes correctly; response formatting
handles goal/hyps; a guarded real-server smoke test skips cleanly when Lean
is unavailable.
**Verification level**: ✅ Unit + ✅ Real (smoke test against `lean --server`
if the environment allows; skipped otherwise).

---

## Item 9 — Docs + honest external-dependency notes
**Scope**: README/GUIDE updates for new commands/env vars; `PROPOSALS.md`
checkoffs; a short "What we have NOT yet verified" section so no claim outruns
its evidence.
**Acceptance**: README lists `prover formalize`, `synth-data`, `--n-attempts`,
`PROVER_RETRIEVE`; honest-limitations section present.
**Verification level**: ✅ Unit (doc lint / consistency check).

---

## Explicitly deferred (documented, do not attempt here)
| Item | Why deferred |
|---|---|
| Mathlib/toolchain bump (v4.20 → current, adds `grind` **and the `runTactic` RPC**) | Rebuilds the pinned benchmark; ~1h fetch + risk of breaking all 317 tests / 68 score. `runTactic` (Item 8) becomes live only after this. |
| Full MiniF2F/PutnamBench benchmark run | The 244 MiniF2F `test` statements are imported + type-checked (Item 1); *proving* them needs model tokens + hours. |
| Real RL fine-tune on synth data | Needs GPU/API budget. Pipeline lands in Item 7. |
| Live-model numbers for Items 2/4/5/6 | The configured HF endpoint hangs on `/chat/completions`; re-run when it serves inference. |
| Contribute to mathlib / Erdős open problems | Community + long-running process; the 2026 Erdős 728/347/369 solves are the model. GUIDE §9 already points here. |

---

## Order & dependencies
1 (tooling) → 2 (search) → 3 (retrieval) → 4 (router) → 5 (formalize) →
6 (lemma-plan) → 7 (synth) → 8 (LSP primitive) → 9 (docs) → final double-verify.
Items 2–7 all build on the existing `prove()` signature and are additive;
nothing is rewritten.
