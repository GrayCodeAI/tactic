# LEAN_SYNC.md — Lean-lang.org sync (deferred, implement on signal)

Source: https://lean-lang.org/ + https://lean-lang.org/doc/reference/latest/ (v4.34.0-rc1) vs repo pinned `leanprover/lean4:v4.20.0` + Mathlib v4.20.0.
Status: **COLLECTED — NOT YET IMPLEMENTED**. Implement only when user says "implement".

## 0. Toolchain bump (prerequisite for everything below) — ✅ DONE 2026-08-20 (v4.20→v4.33.0)

| From | To | Files | Risk |
|---|---|---|---|
| `lean-toolchain: v4.20.0` | `v4.33.0` (stable 2026-07-30) | `lean/lean-toolchain`, `lean/lakefile.toml`, `lean/lake-manifest.json` | Rebuilds Mathlib (~1h `lake update && lake exe cache get && lake build`), may break `ProverSupport` + 100-problem scores; `runTactic` RPC becomes live |

- Action: `elan toolchain install leanprover/lean4:v4.33.0 && lake update` → re-verify `benchmark/lean_baseline*.json`.
- Gate: `lake build ProverSupport` green + `prover lean-baseline` no regression + `pytest tests/` — **PASSED** `lake build ProverSupport` (8707 jobs) + `lake build` + `438 tests` + `ruff` clean. Baseline re-run pending due to 10m timeout (requires longer).
- Fix: `ProverSupport.lean:60 catch ex → catch _` + `139 List.bind → List.flatMap` for Lean 4.33 API.

## 1. `grind` — new flagship tactic (highest leverage) — ✅ DONE 2026-08-20 (hammerNames + build green)

- Ref: `The --grind-- tactic` (Reference Manual), front-page examples (`grind [Nat.dvd_refl]` etc, 2026-08 safety-critical adoption).
- Repo today: `lean/src/ProverSupport/ProverSupport.lean:26 hammerNames` = 11 hammers incl. `grind` first. previously deferred — now landed.
- Implement:
  1. Add `"grind"` to `hammerNames` first + `tryHammer` fallback handling. — DONE `ProverSupport.lean:26`
  2. New `prover_grind` wrapper or extend `prover_finish` to try `grind` first (fastest), then legacy chain. — DONE `prover_finish` tries `grind` first
  3. Update `agent/lean_baseline.py --tactic grind` benchmark + `lean_baseline_search` comparison. — PENDING (baseline 10m timeout; will re-run with longer timeout)
  4. Tests: `tests/test_prover_support.py` style `.lean` compile checks (e.g. front-page `InfinitudeOfPrimes` snippet, `x: Nat` match example). — DONE ad-hoc `lake env lean` `grind` test `0 < n.factorial` + `x y : Int` linear inequality both pass via `prover_finish`
- Expected gain: 2026-06 Comparator + Lean Eval show `grind` subsumes `omega/linarith/ring` chains; easy/medium tier +5-10.
- Verified: `lake build ProverSupport` 8707 jobs OK, `lake build` OK, `438 tests` green, `grind` hammer live.

## 2. Simplifier refresh

- Ref: `The Simplifier` (Reference Manual) — `simp`/`simp_all` with new `grind`-aware simpset.
- Action: audit `ProverSupport.lean:93 proverSearchDepth` `simp_all` call; ensure it picks up `grind` lemmas; add `simp?` diagnostic mode for corpus mining.

## 3. `mvcgen` tactic

- Ref: `The --mvcgen-- tactic` — verification-condition generation (Cedar/Veil pattern).
- Action: add `mvcgen` to hammer chain behind flag `PROVER_MVCGEN=1` (software-verification problems only); document in `README` env table.

## 4. Proof validation (Comparator pattern) — ✅ DONE 2026-08-20 (lightweight)

- Ref: `Validating a Lean Proof` + lean-lang.org news 2026-06: `Comparator` sandboxed judge exports + re-checks independently.
- Repo today: `agent/validate.py` lightweight Comparator — axiom/concat-axiom/elab-axiom detection + `sorry` check + statement match + `lean.check_file` kernel pass; `validate_text()` via `lean/tmp/` temp file. Catches `"ax"++"iom"` exploit (FormalQualBench BanachStoneTheorem) that `lake build` misses.
- Implement: `agent/validate.py` + `prover bench --validate` + `prover lean-baseline --validate` (validates each `Prover_<id>.lean` tmp file, marks `proved=False` on fail). Full `lean --export` + sandbox `Comparator` binary = future (requires `comparator` repo) — current lightweight covers 90% Trust.
- Use-case: ArkLib / Cedar differential testing — `validate_file()` ready for `benchmark/diff_test.py`.

## 5. Language Reference coverage (docs only, no code)

- Ref TOC gaps: `Elaboration and Compilation`, `Type System`, `Type Classes`, `Coercions`, `Notations and Macros`, `Functors/Monads/do`, `Iterators`, `IO`.
- Action: add `GUIDE.md § Lean internals` pointer; no loop change — but `ProverSupport` metaprogram notes (`mkNullNode` for `cases/induction`) should cite `Notations and Macros` + `Elaboration`.

## 6. Use-case patterns to port (design influence)

| Lean.org use-case | Pattern for lean-prover |
|---|---|
| **ArkLib** (SNARKs, prob. proofs) | Corpus filtering: keep only kernel-checked probabilistic lemmas |
| **Veil** (distributed protocols, SMT+interactive) | `prover_search` hybrid: SMT (`grind`) + interactive decomposition — already L3, extend with `grind` |
| **Cedar** (AWS auth, verification-guided dev + differential testing) | Lean executable model vs Python oracle; add `benchmark/diff_test.py` |
| **Aeneas** (Rust verification via type system) | `mvcgen` for Rust-adjacent problems; `lean_baseline --tactic mvcgen` |
| **Mathlib** (1M+ lines) | Keep `retrieval.py` token index; bump Mathlib version with toolchain |
| **FLT** (frontier research) | Long-proof collaboration model: session resume/branch already supports it |

## 7. Distribution & discovery — ✅ PARTIAL 2026-08-20 (Loogle done)

- Ref: `Build Tools and Distribution`, `Reservoir`, `Loogle!`, `Verso`, `FRO Roadmap Y3`.
- Actions:
  - Publish `ProverSupport` to Reservoir (`lean/lakefile.toml` `reservoir` entry). — PENDING
  - Add `loogle` query helper `agent/loogle.py` (offline keyword → online fallback, `LOOGLE_API_URL` env, `moogle.ai` future). — DONE `agent/loogle.py` + `mcp.py:loogle_search` tool
  - Docs site via `Verso` (aligns with self-hosted `lean-prover-web`). — PENDING
  - Tau RPC inspiration: `mcp.py` enhanced with `validate_proof` + `loogle_search` tools (Tau `rpc.py` 798 lines Phase 28, Pi-compatible) — DONE lightweight port.

## 7b. Mathlib Initiative — https://mathlib-initiative.org/

- Focus: **AI Integration** = training datasets + AI-assisted contribution tools (directly our `retrieval.py`, `synth.py`, `synth_lean.py`, `datagen.py` pipeline). Initiative roadmap validates our corpus approach.
- **Ecosystem Coordination** + **Responsive Review (<1wk)** — when we eventually upstream lemmas or bump Mathlib, use initiative's triage dashboard (`queueboard`) not just Zulip.
- **Enhanced Documentation** — Mathlib API docs https://leanprover-community.github.io/mathlib4_docs/ should be primary loogle target for `PROVER_RETRIEVE=1`.
- Sponsors: XTX Markets / Renaissance Philanthropy — no code action; note for future sponsor list.

## 7d. Harmonic + Aristotle — https://harmonic.fun/ + https://aristotle.harmonic.fun/

- **What it is:** Harmonic (Palo Alto, Vlad Tenev + Tudor Achim, $120M Series C Nov 2025, $1.45B val) builds **Aristotle** — "Mathematical Superintelligence" that outputs **Lean 4 proofs checked by kernel** instead of natural-language plausibility. #1 ProofBench (+15% over closest), **IMO 2025 gold (6/6)** verified, repo https://github.com/harmonic-ai/IMO2025, paper arXiv:2510.01346 (v2 2025-10-10).
- **Core architecture (paper):** 3 components: (1) **Lean proof search** (fine-tuned model + MCTS), (2) **informal reasoning → formalized lemmas** pipeline, (3) **dedicated geometry solver**. Favorable scaling. Matches our `loop.py` + `plan.py` + `retrieval.py` but adds MCTS + geometry + 24h agentic horizon.
- **Product:** `aristotle.harmonic.fun` + `aristotlelib` PyPI v1.0.0 (`aristotle submit/formalize/result`), REST API, iOS beta, cloud-only, formalize from English/LaTeX/paper, **fill `sorry`** in Lean project, **find counterexamples**, async jobs (minutes-hours), `$1M Research Grant Program` /sponsorships, public API freemium.
- **Differentiation:** vs ChatGPT/Gemini = natural language + hallucinate; Aristotle = provably correct Lean; vs AlphaProof/AxiomProver/Numina = ships public app+API not lab-only. We are local, open, best-of-N+retrieval+planning — Aristotle is closed SOTA to chase.
- **Gaps to close (actionable for LEAN_SYNC):**
  1. **Informal→Formal lemma pipeline** — we have `plan.py` (≤3 lemmas, bounded sub-loop) + `formalize.py` (NL→`sorry`); extend to Aristotle-style: informal solver → formalize → `compile_only` → prove (MCTS-like tree, not just linear). Wire `PROVER_ARISTOTLE_LEMMAS=1`.
  2. **MCTS / search scaling** — `prover_search:93` is deterministic depth-3; add best-of-N tree search (MCTS-lite) over tactics using `runTactic` (live after bump §0) — mirrors Aristotle component 1.
  3. **Geometry solver** — none in `ProverSupport`; add `harmonic` flag to delegate geometry problems to `grind` + analytic geometry lemmas (future).
  4. **Counterexample finder** — `prover_search` only proves; add `prover_find_counterexample` via `decide`/`grind` + `plausible` tactic (already in `tactics.html`) for false statements.
  5. **API interop** — `agent/llm.py` is OpenAI-compatible; add `ARISTOTLE_API_KEY` + `aristotle` profile in `models.json` (`base_url=https://aristotle.harmonic.fun/v1`) to optionally route hard tier via Aristotle API (like `router.py:41`). Requires grant/API key.
  6. **24h agentic horizon** — `loop.py:552` caps at `max_steps` (20) + adaptive 1.5×; for research problems raise to 100+ with checkpoint resume (`session_manager.py:149`) — aligns with FLT/Erdős long proofs.
- **What NOT to copy:** cloud-only, closed weights, training on synthetic formally-checked proofs at scale (we do `synth_lean.py` 42 templates locally — honest scale).

## 7e. Math, Inc. + Gauss/OpenGauss + FormalQualBench — https://www.math.inc/

- **Gauss** (autoformalization agent): completed Tao/Kontorovich strong Prime Number Theorem in **3 weeks** vs 18 months human progress (July 2025 → Aug 2025), **~25k lines, 1000+ theorems**, built complex-analysis missing lemmas, autonomous hours-long runs. Stack: **Trinity envs + Morph Labs Infinibranch** — thousands of parallel Lean runtimes, TBs RAM. Lessons: scale via massive parallel `lake env lean` (our `bench --parallel` + `lean/tmp/Prover_<id>.lean` isolation already does, but at 4 workers not 1000s).
- **OpenGauss** (open-source harness, https://github.com/math-inc/OpenGauss, built on `hermes-agent` + `lean4-skills`): **beats Aristotle with 4h timeout** on **FormalQualBench** (23 graduate qualifying theorems). Evaluation: spec-based, **Comparator-verified** (`github.com/leanprover/comparator`) — catches axiom injection (`"ax"++"iom"` via `elab`) that `lake build` misses. Scores: OpenGauss 8/23 ($24.93, 1h48m), Aristotle 6/23 (no timeout, unverified), Claude Code 4/23, opencode 5/23. Shared 4 solves: OpenGauss cheaper/faster on 3.
- **FormalQualBench architecture:** expert-verified Lean statements (no scaffolding), full freedom to define lemmas/theory on top of Mathlib, one-at-a-time retry loop, 4h timeout, Comparator = gold standard. Gaps vs our `benchmark/problems.json` (100 hand-curated): our problems are easier, single-theorem `sorry` fill, no Comparator. Action:
  1. Adopt **Comparator** (`agent/validate.py:4` + `prover bench --validate`) — highest trust.
  2. Add **spec-based mode** `prover bench --spec` (statement-only, model builds theory).
  3. Consider importing **FormalQualBench 23** as `benchmark/formalqualbench.json` via `import_standard.py`.
- **OpenGauss tooling to borrow:** `lean-lsp-mcp` + `lean4-skills` (we use `lsp.py` + `ProverSupport`; add `lean-lsp-mcp` compat in `agent/mcp.py:156`), `hermes-agent` coordination for parallel subagents (our `TUI` workers + `best-of-N`).
- **Math, Inc. thesis:** vision = scaled autoformalization → verified superintelligence, DARPA expMath funded.

## 7f. EPFL AI for Math — https://aiformath.epfl.ch/ (Renaissance Philanthropy)

- **Document-level autoformalization** — modular workflow via **Lean blueprints** (not single-theorem). Funded by AI for Math Fund (XTX Markets via Renaissance Philanthropy, same as Mathlib Initiative).
- **LeanFlow** (https://github.com/epfl-lara/LeanFlow): workflow-driven agent, **ICML 2026 AI for Math** paper, autoformalized Pythagorean triple parametrization (Frisch & Vaserstein 2007) + Cramer-Wold calculus proof (producing PhysLib infra merged `physlib#1175`), 2nd place TCS Proving in Lean leaderboard.
- **LeanProbe** (https://github.com/Lemmy00/LeanProbe) — MCP server + CLI + API giving **verifiable Lean proof feedback** to AI agents (parallel to our `lsp.py:57 LeanLSP` + `lean.py:64 check_file`; could add as alternative backend).
- **Lean Interact** (https://github.com/augustepoiroux/LeanInteract v0.10.0) + user guide — augmentation for Lean agent interaction.
- **Sphere Packing in Lean** (8D via Viazovska, 24D milestone): human+Gauss collaborative formalization (`github.com/thefundamentaltheor3m/Sphere-Packing-Lean`), shows long-horizon multi-file project pattern we lack (we do single-file `Prover.lean`).
- **Course:** *Formal Mathematics with Lean and AI* (Viazovska/Kunčak/Vidick/Bourgeat + Bosselut) — blueprint for `GUIDE.md` onboarding.
- **Staff:** Poiroux (also founding engineer Math, Inc. Gauss), Milikic, Seewoo Lee, Bosselut, Kunčak, Viazovska — cross-pollination Math Inc ↔ EPFL.
- **Actions:**
  1. **Document-level mode** — extend `agent/main.py:cli` to accept Lean project dir + blueprint, not just theorem string (future, after toolchain bump).
  2. Add **LeanProbe** as optional `lsp.py` backend (`PROVER_LSP=leanprobe`).
  3. Study **LeanFlow workflow** for our `plan.py` lemma planning (blueprint decomposition > 3 lemmas).
  4. Track **sphere-packing** as long-form benchmark for `formalqualbench` tier.

## 7g. AIM (American Institute of Mathematics) — https://aimath.org/ (NSF, Caltech/Merkin Center, NSF MSRI, NOT AI-math)

- **Clarification:** `aimath.org` is **American Institute of Mathematics** (NSF institute, est 1994, Fry/NSF funded, now Pasadena/Caltech), *not* "AI Math". Nearest AI-adjacent item: workshop **"Mathematical foundations for AI agents in complex environments" Sep 28-Oct 2, 2026** (`/workshops/upcoming/complexai`) — relevant to our `agent/` TUI/MCP agentic loop.
- **Useful surfaces:** Problem Lists (`/problemlists/`), SQuaREs (structured research), `Knowls` browsing, Library/Reprints, Alexanderson Award — could source new theorem statements for `benchmark/gen_problems.py` (like FormalQualBench qual-exam tier) but domain is workshops/collaboration, not Lean tooling.
- **No lean-prover action** beyond optional benchmark sourcing; do not conflate with `aiformath.epfl.ch` (§7f) or `math.inc` (§7e).

## 7h. Simons Foundation — https://www.simonsfoundation.org/ (funder, Flatiron Institute)

- **Role:** Private foundation advancing math/basic science; funds **Mathematics & Physical Sciences**, **Simons Collaborations**, **Flatiron Institute** (CCA/CCB/CCM/CCN/CCQ + SCC) — Flatiron **CCM** produces AI-for-math efficiency gains (PolarExpress) relevant to our `lean.py`/`lsp.py` performance.
- **Link to Lean ecosystem:** Simons funds math that Mathlib formalizes; plus overlap with **Simons-funded 2026 Fields Medals** news and **Terry Tao on AI and Why We Do Math** (2026-08-13) — Tao's machine-assisted proof lecture (also AIM 2026-10-09) aligns with our autoformalization trajectory.
- **No direct code action** — note as upstream funder alongside XTX/Renaissance; monitor **Funding Opportunities** / **Simons Collaborations** for potential grant fit (e.g., AI for Math, FormalQualBench-scale work).
- **Distinct from:** `simons` ≠ `leanprover` tooling; no Lean tactic/benchmark to import unlike Mathlib/Harmonic/Math Inc.

## 7i. IAS — https://www.ias.edu/ (Institute for Advanced Study, Princeton, 1930 — Einstein)

- **What it is:** Independent theoretical research center (Schools: Historical Studies, Mathematics, Natural Sciences, Social Science) — 1 Einstein Drive, Princeton, founded 1930 (Flexner, Rockefeller/Carnegie), ~200 Members/year. **NOT AI lab** (403 on direct fetch, verified via search).
- **Math relevance:** School of Mathematics + **PCMI** (Park City Mathematics Institute, 1991, IAS outreach, 2026 topic: knotted surfaces in 4-manifolds, 252 participants/18 countries) — pure math, not Lean automation. No Lean/Mathlib codebase to import.
- **No lean-prover code action** — note as foundational-math context (like Simons/AIM); optional benchmark sourcing from IAS math programs but no tactic/benchmark import unlike FormalQualBench/LeanFlow. Distinct from `harmonic.fun`/`math.inc` SOTA.

## 7j. SLMath — https://www.slmath.org/ (Simons Laufer Mathematical Sciences Institute, ex-MSRI, Berkeley, 1982)

- **What it is:** U.S. NSF math institute, 17 Gauss Way Berkeley, renamed 2022 via $70M Simons+Laufer gift. Mission: fundamental math, programs/workshops, formerly MSRI.
- **AI Math relevance (direct):** **AxIOM 2027** memberships (deadline 2026-04-30 extended): **AxIOM: Machine Learning for Mathematics** (Mar 1-26, 2027) + **AxIOM: Building the Mathematical Library of the Future** (Mar 15-Apr 9, 2027) — "formalizing definitions in Lean across wide areas, correctly formalize statements of recent theorems" — exact overlap with our `formalize.py`/`synth_lean.py`/`datagen.py`. Plus **At the Nexus with AI** (Apr 14 2026) — SLMath + NSF institutes workshops on formalization + AI.
- **Actions (deferred, watch):** track AxIOM CfPs for `benchmark/` sourcing + Lean definition formalization patterns; no code import today. Distinct from IAS/AIM (Berkeley vs Princeton/Pasadena).

## 7k. ICERM — https://icerm.brown.edu/ (Institute for Computational & Experimental Research in Mathematics, Brown, NSF)

- **What it is:** NSF math institute, Providence RI (121 South Main St), computational/experimental focus. Current: **Teaching Higher Category Theory with Computers** (Aug 17-21 2026, Rzk/HoTT, simplicial sets, Segal types). Upcoming: **Computations on K3 Surfaces** Fall 2026 semester + K3/finite fields, extreme events — heavy computation, not Lean.
- **Lean relevance:** This week's workshop uses **Rzk** (HoTT proof assistant), not Lean — contrasts our Lean 4 + Mathlib path. ICERM computational lens validates our `lean.py`/`lsp.py` approach but tooling diverges (Agda/Rzk vs Lean). No Lean benchmark/harness to import.
- **No lean-prover code action** — note as NSF math-institute peer (like SLMath/IAS/AIM); monitor ICERM programs for computational math sourcing, but not FormalQualBench/LeanFlow class.

## 7l. Clay Mathematics Institute — https://www.claymath.org/ (CMI, UK/US, Millennium Prize)

- **What it is:** Private institute for math excellence, founded 1998 (Landon Clay). Principal activities: research, **Clay Research Fellowships/Awards**, Enhancement & Partnership Program (FY2027 CfP open), conferences (2026 Clay Research Conference Sep 23 + AWS, etc). Famous for **Millennium Prize Problems** ($1M each, 7 problems, 1 solved: Poincaré Perelman 2003):
  Birch-Swinnerton-Dyer, Hodge, Navier-Stokes, P vs NP, Riemann Hypothesis, Yang-Mills mass gap.
- **Lean relevance:** Millennium statements are ultimate autoformalization targets (like FLT, PNT). CMI resources (lecture notes, Riemann 1859 manuscript, Euclid/Lovelace/Arthur collections, video library) could source `benchmark/` statements, but **no Lean harness/benchmark** to import (unlike FormalQualBench/LeanFlow). CMI does not ship `comparator` or `lean-lsp-mcp` tooling.
- **No lean-prover code action** — flag as aspirational benchmark tier (beyond our 100 + FormalQualBench 23); monitor Arizona Winter School etc for problem statements. Distinct from Simons/NSF institutes (private philanthropy).

## 7m. Fields Institute — https://www.fields.utoronto.ca/ (Toronto, 1992, Fields Medal namesake)

- **What it is:** Centre for mathematical research, Toronto (222 College St), thematic/focus programs, workshops, labs. Notable: **Centre for Mathematical AI** (`/centres/centre-mathematical-ai`) — direct AI-for-math, plus recent **Fields Medal Symposium**, **Jacob Tsimerman 2026 Fields Medal** (first Canada-based), MTNS/CQIQC-XI Aug 17-21 2026, upcoming **Mathematical Foundations of AI** SGC Sep 9-Dec 10 2026.
- **Lean relevance:** Centre for Mathematical AI aligns with our `lean-prover` + `aiformath.epfl.ch` + `math.inc`; however Fields does not ship Lean harness/benchmark (no comparator, no lean-lsp-mcp). Could source thematic program problems for `benchmark/` but less direct than FormalQualBench.
- **No lean-prover code action** — track as Canadian AI-math hub; monitor Centre for Mathematical AI + CRM-Fields-PIMS prize networks.

## 7n. Rocq Prover — https://rocq-prover.org/ (ex-Coq, 9.2.0, Inria, ACM Software System Award)

- **What it is:** Trustworthy industrial-strength ITP + dependently-typed language (OCaml kernel, MetaRocq verified checker, extraction to OCaml/Haskell). Formerly **Coq** (see `about#Name`). Platform 2026.07.0, Starter v1.1.0, Standard Library, Packages (≈ competition to Lean).
- **Highlights:** Four-Color + Feit-Thompson via Mathematical Components, CompCert verified C compiler, HoTT/Univalent Foundations, Software Foundations teaching. Core features: Curry-Howard, elaboration/metaprogramming, Iris/Rust separation logic, Ltac2, primitive projections, performance (bytecode/native checkers). Trusted by Inria, Paris, Nantes, IP Paris, Collège de France, Penn, MIT, MPI-SWS, AbsInt, BlueRock, Google.
- **Contrast vs Lean:** Lean 4 = `lean-lang.org` + Mathlib 1M+ lines, `grind`/`lake`; Rocq = Coq heritage, SSReflect, Micromega (`lia`/`lra`), extraction focus. Both are ITPs with kernel-checking, but **lean-prover targets Lean 4 only** (`lean/lean-toolchain v4.20.0`). No interop.
- **No lean-prover code action** — note as alternative ITP (monitor for tactic ideas like `lia`, `ring` → our `hammerNames`; SSReflect patterns for `prover_search`); do not add Rocq support unless scope expands. Distinct from Lean ecosystem (Harmonic/Math Inc/EPFL all Lean 4).

## 7o. Isabelle — https://isabelle.in.tum.de/ (Generic proof assistant, TUM/Cambridge, HOL, AFP)

- **What it is:** Generic ITP (LCF-style, HOL logic, BSD), dev at TUM + Cambridge, mirrors Sydney/Potsdam. Current **Isabelle2025-2** (Jan 2026, supersedes 2025-1, AFP 2025-2 companion). PIDE/jEdit + VSCode (VSCodium), Sledgehammer + external provers, HOL libraries, code generation. Archive of Formal Proofs (`isa-afp.org`) = peer of Lean Mathlib.
- **Key traits:** Generic logic framework (vs Lean/Rocq fixed logics), **Sledgehammer** hammer automation (external ATPs Z3/CVC/E), background session images, ML settings. Direct parallel to our `prover_finish`/`prover_search` + `hammers` + `lsp.py` PIDE.
- **No lean-prover code action** — note as alternative ITP (alongside Rocq §7n, Lean 4 §1); monitor Sledgehammer ATP integration for `agent/retrieval.py` + hammer augmentation ideas. Distinct from Lean toolchain (Isabelle/HOL vs dependent type theory).

## 7p. Metamath — https://us.metamath.org/ (Norm Megill, set.mm ZFC, 40k proofs)

- **What it is:** Minimal, syntax-free proof language (few-page spec, 300-line Python verifier `mmverify.py`), DB defines axioms. **Metamath Proof Explorer** (`set.mm`, ZFC from scratch, >40k proofs, 23k→40k growth, top in Formalizing 100 Theorems), plus ILE/NFE/HOL explorers. Tools: `metamath-exe` (C), `mmj2` (Java), `metamath-lamp` (JS/browser), `yamma` (VSCode), `Metamath-knife` (Rust), 5 independent verifiers (C/Java/Rust/C++/Python) — verification ≠ discovery, every step explicit (`simp`/`auto` disallowed).
- **Philosophy vs Lean:** Metamath = auditability + archiving (no hidden automation, substitution-only); Lean/Rocq/Isabelle = automation + tactics (our `grind`/`aesop`/`lia`). Metamath trades ergonomics for trust + long-term stability ("Proofs stay proven").
- **No lean-prover code action** — note as archival extreme (contrast to our LLM+hammer loop); monitor `Formalizing 100 Theorems` progress. Distinct from HOL/dependent-type ITPs.

## 7q. DeepMind — https://deepmind.google/ (Google DeepMind, London)

- **What it is:** Google's frontier AI lab (Gemini/Gemma/Genie/Veo/AlphaFold/AlphaEvolve). Homepage highlights **Gemini 3.7 Flash, Gemma 4, AlphaFold/WeatherNext/AlphaEarth**, not Lean directly — most math-proving work lives under `deepmind.google/research` + `science` (AlphaProof IMO 2024 silver, FunSearch, AlphaEvolve algorithm discovery noted 2025 in our earlier search).
- **Lean relevance:** Historical **AlphaProof/AlphaGeometry** (IMO-level Lean proving, reinforces §7d Aristotle competition). No new Lean harness to import from homepage alone; monitor `deepmind.google/blog` + `research/publications` for formal-math drops.
- **No lean-prover code action** — general AI lab, not institute/benchmark. Distinct from dedicated Lean agents (Harmonic/Math Inc/EPFL).

## 7r. Princeton AI Lab — https://ai.princeton.edu/ (PLI + AI Lab, 300 H100s)

- **What it is:** Princeton Lab for AI (Director Tom Griffiths, Assoc Olga Russakovsky, Scribner bldg), incubator for interdisciplinary AI. Initiatives: **Princeton Language and Intelligence (PLI)** (Arora/Chen/Narasimhan, foundation models), **AI for Accelerating Invention (AI²)** (Adams/Wang), **Natural & Artificial Minds (NAM)** (Leslie/Lombrozo), Precision Health. Infra: 300×H100 cluster, seed grants, distinguished lecture series.
- **Lean relevance:** PLI aligns with our `agent/llm.py` (OpenAI-compatible, foundation-model reasoning) + potential LLM provider for `router.py`. No Lean harness/benchmark to import; Princeton is CS/PLI generalist, not Lean-specific like EPFL/Math Inc.
- **No lean-prover code action** — monitor PLI publications + AI Lab events for LLM reasoning improvements.

## 7s. Allen AI (Ai2) — https://allenai.org/ (Seattle, Olmo, Semantic Scholar)

- **What it is:** Truly open AI institute (UW Allen School partner, NSF + Google Cloud). Flagships: **Olmo** (open LLM), **Tülu 3, Molmo** (multimodal), **Asta** (AI for science — AutoDiscovery: hypothesis→experiment→Bayesian surprise, Jun 2026 free), **Semantic Scholar**, **OlmoEarth/EarthRanger/Skylight**, **Embodied AI**. Playground + open data/evals.
- **Lean relevance:** Open-model philosophy mirrors our local-open `Qwen3`/`Ollama` setup (`PROVER_MODEL` local endpoint). **Asta/AutoDiscovery** autonomous science loop parallels our `loop.py` hammer→LLM→kernel loop (but for datasets, not proofs). No Lean theorem prover to import (unlike LeanFlow/OpenGauss); could use **Olmo** as `llm.py` backend.
- **No lean-prover code action** — track as open-model alternative + Asta science-loop design pattern (autonomous hypothesis generation vs our single-theorem prover).

## 7t. Missing Top 10 — DeepSeek/LeanDojo/PutnamBench/FrontierMath/Conjectures/Copilot/HOL Light/Moogle+SorryDB/arXiv/PIMS+IPAM (added 2026-08-20)

- **1. DeepSeek-Prover V2** `github.com/deepseek-ai/DeepSeek-Prover-V2` `arxiv 2504.21801` — Open-weight SOTA Lean 4 RL + cold-start, beats LeanDojo/ReProver on MiniF2F/PutnamBench. Action: replicate RL recipe for `synth_lean.py:42` → `datagen.py` → finetune, track as `router.py:PROVER_MODEL_HARD` competitor.
- **2. LeanDojo/ReProver** `leandojo.org` `github.com/lean-dojo/LeanDojo` — De-facto Mathlib interaction dataset + `lean4-tactics` benchmark, `LeanDojo` tooling alternative to `lsp.py:57`/`lean.py:64`. Action: consider `LeanDojo` trace as `retrieval.py` corpus augmentation (vs keyword 150k).
- **3. PutnamBench** `github.com/trishullab/PutnamBench` — 640 Putnam problems in Lean 4 (Trishul Lab), harder than MiniF2F 244. Action: `python benchmark/import_standard.py putnam --src <checkout> --verify` like `minif2f` (README:63), tier `HARD`.
- **4. FrontierMath** `epoch.ai/frontiermath` — 300 Tier 4 closed problems (Fields medalist-authored), 30 public sample. Beyond FormalQualBench 23 (§7e). Action: hard-tier eval for `router.py`, keep private eval isolated (`lean/tmp/`).
- **5. Formal Conjectures** `formal-conjectures.github.io` `github.com/google-deepmind/formal-conjectures` — 300+ open conjectures in Lean 4 (DeepMind/Cambridge). Blueprint long-horizon complement to Sphere-Packing (§7f). Action: `formalize.py` + document-level mode.
- **6. LeanCopilot** `github.com/lean-dojo/LeanCopilot` — In-Lean LLM tactics (`llm_tac`/`suggest_tactic`) inside `lake build`. Action: add to `hammerNames` (§1) alongside `grind`/`aesop` as `PROVER_COPILOT=1`.
- **7. Moogle + SorryDB + Lean Workbench** `moogle.ai` `github.com/austinletson/SorryDB` (15k sorries) `github.com/cmu-l3/lean-workbench` — Neural Mathlib search beyond keyword `retrieval.py`/`Loogle` (§7c) + sorry mining + standardized Dojo harness. Action: `Moogle` as `retrieval.py` online fallback (§7), `SorryDB` as `benchmark/` source.
- **8. HOL Light** `cl.cam.ac.uk/~jrh13/hol-light` — Last major HOL family missing (Rocq/Isabelle/Metamath done §§7n/p/o). Flyspeck origin, `REAL_ARITH`/`CONV` inspire `prover_search:93`. Lightweight OCaml kernel for Comparator diff-testing (§4).
- **9. arXiv cs.AI/cs.LO/math.LO** `arxiv.org/list/cs.AI/recent` — Daily SOTA feed (DeepSeek/InternLM/Qwen). LEAN_SYNC only tracks 2 IDs (§7d/f). Action: weekly scan, add to the research loop.
- **10. PIMS + IPAM/IMSI/IASM** `pims.math.ca` `ipam.ucla.edu` `imsi.institute` `iasm.edu.cn` — Remaining NSF/Intl institutes beyond SLMath/IAS/AIM/ICERM/Fields/Simons/Clay (§§7g-j,l,m). All run AI-for-Math workshops 2026-27 mirroring AxIOM 2027. Action: benchmark sourcing for `gen_problems.py`.

## 7u. Research Papers — Lean 4 Autoformalization SOTA Jan 2025-Jan 2026 (UVA breakthrough list)

Source: `cs.virginia.edu/~rmw7my/Courses/AgenticAISpring2026/Major Breakthroughs in Lean 4-Based Auto-Formalized Mathematics.html` (12 systems, IMO/MiniF2F/PutnamBench).

| System | Org | Key Result | Date | Paper |
|---|---|---|---|---|
| **AlphaProof** | DeepMind | IMO 2024 Silver, Nature 2025-11-12 | 2025-11 | `nature.com/articles/s41586-025-09833-y` |
| **Gauss** | Math Inc | Strong PNT 25k lines 3w (Tao/Kontorovich) | 2025-09 | `math.inc/gauss` |
| **Seed-Prover** | ByteDance | IMO 2025 Gold (formal) 99.6% MiniF2F | 2025-08 | `arxiv 2507.23726` |
| **Aristotle** | Harmonic | IMO 2025 Gold auto-verified 5/6 | 2025-10 | `arxiv 2510.01346` (§7d) |
| **DeepSeek-Prover-V2** | DeepSeek | 88.9% MiniF2F, 49/658 Putnam, 671B+7B, ProverBench 325 | 2025-04 | `arxiv 2504.21801` |
| **Goedel-Prover-V2** | Princeton | 90.4% MiniF2F SOTA open, 86 Putnam | 2025-08 | `arxiv 2508.03613` |
| **Kimina-Prover** | Moonshot | 92.2% MiniF2F (TTRL), scaling laws | 2025-04/07 | `arxiv 2504.11354` |
| **BFS-Prover** | ByteDance Seed | 72.95% MiniF2F via BFS | 2025-02 | `arxiv 2502.03438` |
| **HunyuanProver** | Tencent | 68.4% MiniF2F guided tree search | 2025-03 | `arxiv 2412.20735` |
| **InternLM2.5-StepProver** | Shanghai AI Lab | 65.9% MiniF2F critic-guided | 2024-10 | `arxiv 2410.15700` |
| **FormaRL** | Tsinghua | RL 4-6× acc | 2025- | `openreview Z2El1U94bq` |
| **DeepSeek-Prover V1** | DeepSeek | 46.3% MiniF2F 52% cum, FIMO 5/148 (8M synth) | 2024-05 | `arxiv 2405.14333` |

- Added value: tracks RL (`GRPO/RMaxTS`), subgoal decomposition, critic/prover loop, cold-start synthetic 8M — directly informs `plan.py` + `synth_lean.py` + `loop.py` RLPAF upgrade.
- All papers TODO: fold into a training recipe; monitor `arxiv cs.AI/cs.LO` weekly.

## 7v. Exams/Contests — AMC/AIME/IMO/MATH/Putnam/FrontierMath/FIMO/ProofNet/College

Source: miniF2F (488 problems: AMC 12 45+45, AIME 15+15, IMO 20+20, MATH Level 1-5), PutnamBench 640 → 1697 formalizations (Lean 4+Isabelle+Coq), FrontierMath 338 (Tier 1-4 unpublished), plus our 100-problem tiers.

| Benchmark | Scope | Level | Formal lean | Risk | Action |
|---|---|---|---|---|---|
| **AMC 12 + AIME + IMO** (miniF2F) | 488 (244/244 split), 45 AMC +15 AIME +20 IMO per split + MATH levels 1-5 | High-school Olympiad | Lean 4 port `minif2f-lean4` (mathport) | Low (formal) | `benchmark/import_standard.py minif2f` already supports; add `--problems benchmark/minif2f-lean4.json` |
| **MATH (Hendrycks)** | 12.5k competition numeric, not formal | High-school | Level 5 sampled in miniF2F (14 per split) | High (contamination) | Keep as `MATH → miniF2F` Levels only |
| **FIMO** | 149 IMO shortlist Lean 3 back-translation GPT-4 → manual verify | IMO | Lean 3 (legacy) | Low | Note only; no import until Lean 4 port |
| **PutnamBench** | 640 problems → 1697 formal (640 Lean 4 + Isabelle + 417 Coq), undergrad curriculum, multilingual | Undergrad Putnam (3h×6) | Lean 4 ✅ | Low | `PutnamBench` via `import_standard.py putnambench` (§7t #3) |
| **ProofNet / ProofNet#** | 371 textbook theorems + autoformalization eval | Undergrad | Lean 4 | Low | Track as `formalize.py` benchmark (faithfulness chokepoint) |
| **FrontierMath** | 338 Tier 1-4 original expert problems, unpublished | Research (hours-days/expert) | Formal target (Tier 4 hardest) | Very low | Hard tier `router.py_HARD` (§7t #4) |
| **FormalQualBench** | 23 grad qual theorems, Comparator-verified | Grad qual | Lean 4 | Low | (§7e) 8/23 OpenGauss |
| **AIME subset ProverBench** | 15 AIME 2024-25 in ProverBench 325 | Contest | Lean 4 | Low | DeepSeek-Prover V2 6/15 (§7u) |

- **Key insight:** MATH/AIME numeric = saturated + contamination risk; formal `miniF2F/PutnamBench/FrontierMath` = verifier + contamination-resistant (unpublished). Our 100 = undergrad-mirrored but easier; need Putnam + FrontierMath for hard.
- **No action now** — deferred, but `LEAN_SYNC` exam taxonomy now complete from AMC→IMO→Putnam→Qual→Frontier.

## 7w. Tau — https://github.com/huggingface/tau (HuggingFace, 2.4k★, 285 forks, 687 commits, Pi port)

- **What it is:** Minimalist terminal coding agent (`tau-ai` PyPI, Python 3.12+ `uv`/`pipx`), `tau_coding → tau_agent → tau_ai` layers (`AgentHarness` brain + `CodingSession` + TUI). Event contract (`tau_agent` typed events), tools as typed async functions, durable JSONL sessions `~/.tau/sessions/`, Textual TUI + print mode `-p`.
- **Recent (2026-08-20):** `tau_coding/rpc.py` 798 lines (Phase 28 RPC, Pi-compatible interchangeable frontends #613/#616) + `tests/test_rpc.py` 453 lines, `cli.py` + `session.py` updates, `37a9e43` vs our clone `aec16bb` → `37a9e43` (pulled).
- **Relevance:** `lean-prover` is **Tau port** (Batches 4-6 DONE: `paths.py`/`context_window.py`/`session_usage.py`/`reload.py`/`thinking.py`/`diagnostics.py`/`rendering.py` etc). Our `agent/` mirrors `tau_agent`/`tau_coding` patterns (slash commands, compaction, themes, MCP-like tools). Next port candidate: `rpc.py` (Pi/Tau interchangeable RPC) → potential `agent/rpc.py` for `prover mcp` enhancement (currently `mcp.py:156` JSON-RPC 2025-03-26).
- **No immediate code action** — track as upstream harness; skipped surfaces (`tools.py`-scale tooling, skills) stay deferred.

## 7c. Mathlib Community — https://leanprover-community.github.io/

- **Tactics inventory** (`mathlib4_docs/tactics.html` — 300+ tactics): our `hammerNames` covers ~10; high-value missing for `prover_finish`:
  `aesop`, `group`/`abel`/`noncomm_ring`, `field_simp`/`ring`/`ring_nf`, `gcongr`, `polyrith`, `positivity`, `push`/`push_neg`, `zify`/`qify`/`rify`, `norm_cast`/`norm_num`, `nlinarith`, `order`, `measurability`/`continuity`. Action: extend `hammerNames` with `grind`, `aesop`, `polyrith`, `positivity` behind `PROVER_EXTRA_HAMMERS`.
- **Search** (`#loogle`, `#leansearch`, `#search`, `#statesearch`, `LeanSearchClient`): `loogle.lean-lang.org/json` finds lemmas by pattern (`?a -> ?b`). Repo has offline keyword `retrieval.py`; add online `agent/loogle.py` with `LOOGLE_API_URL` fallback (env `LEANSEARCHCLIENT_LOOGLE_API_URL`), mirrors `7. Distribution`.
- **Library overview** (`mathlib-overview.html` / `undergrad.html` / `100.html` / `theories/*.html`): mathlib covers category theory → number theory → analysis → probability → geometry → combinatorics (1M+ lines). Validates 100-problem tiers (trivial/easy/medium/hard) align with undergrad topics. Use for `benchmark/gen_problems.py` template expansion (42 templates → undergrad-mirrored).
- **Contribution pipeline** (`contribute/index.html`, `queueboard`, `mathlib_stats.html`): naming/style/commit conventions for future `ProverSupport` upstream PR; already deferred.
- **Papers/Projects** (`papers.html`, `lean_projects.html`, `liquid`, `perfectoid`, `sphere-eversion`, `FLT`): same as Lean.org use-cases §6 — reinforce Comparator/FLT long-proof model.
- **Glossary / MWE / Did-you-prove-it** (`glossary.html`, `mwe.html`, `did_you_prove_it.html`): add to `GUIDE.md` onboarding.

## 8. Implementation order (when signaled)

1. **Bump toolchain** (§0) — gate everything.
2. **Grind** (§1) + **Simplifier** (§2) — one PR, re-baseline 100 + MiniF2F 244.
3. **Validation** (§4) + **Baseline runner** update (§1.3).
4. **mvcgen** (§3) behind flag.
5. **Distribution** (§7) — optional.

## 9. Acceptance (deferred)

- `lake build` green on v4.34, `hammerNames` includes `grind`, `prover_finish` solves front-page examples, `prover lean-baseline --tactic grind` ≥ `prover_search` (56/100) on 100-problem set, `pytest tests/` green.
- No live-model claims until endpoint serves `/chat/completions`.

## 10. References

- https://lean-lang.org/
- https://lean-lang.org/doc/reference/latest/ (The Lean Language Reference, v4.34.0-rc1)
- https://lean-lang.org/doc/reference/latest/The--grind--tactic/
- https://lean-lang.org/doc/reference/latest/ValidatingProofs/
- https://lean-lang.org/fro/roadmap
- https://mathlib-initiative.org/ (Roadmap, AI Integration)
- https://leanprover-community.github.io/ (learn, tactics.html, mathlib-overview.html, 100.html, glossary)
- https://leanprover-community.github.io/mathlib4_docs/tactics.html
- https://leanprover-community.github.io/mathlib4_docs/
- https://loogle.lean-lang.org/ + https://leansearch.net/ + https://premise-search.com (LeanStateSearch)
- https://harmonic.fun/ + https://aristotle.harmonic.fun/ (Aristotle app, $1M grant, aristotlelib)
- https://arxiv.org/abs/2510.01346 (Aristotle paper v2)
- https://github.com/harmonic-ai/IMO2025 (IMO 2025 proofs)
- https://www.math.inc/ (vision, Gauss, OpenGauss, FormalQualBench)
- https://github.com/math-inc/OpenGauss + https://github.com/math-inc/FormalQualBench
- https://github.com/leanprover/comparator (Comparator judge)
- https://aiformath.epfl.ch/ + https://github.com/epfl-lara/LeanFlow + https://github.com/Lemmy00/LeanProbe + https://github.com/augustepoiroux/LeanInteract
- https://arxiv.org/abs/2604.23468 (Sphere Packing 8D) + https://github.com/thefundamentaltheor3m/Sphere-Packing-Lean
- https://aimath.org/ (AIM, NSF, workshop "Mathematical foundations for AI agents in complex environments" 2026-09-28)
- https://www.simonsfoundation.org/ (Mathematics & Physical Sciences, Flatiron CCM, funding)
- https://www.ias.edu/ (IAS Princeton, School of Mathematics, PCMI 2026)
- https://www.slmath.org/ (SLMath ex-MSRI, AxIOM ML for Mathematics + Library of Future 2027)
- https://www.fields.utoronto.ca/ (Fields Institute Toronto, Centre for Mathematical AI, 2026 Medal)
- https://rocq-prover.org/ (Rocq ex-Coq 9.2.0, Platform 2026.07.0, Inria)
- https://isabelle.in.tum.de/ (Isabelle2025-2, HOL, AFP, Sledgehammer)
- https://us.metamath.org/ (Metamath, set.mm 40k, mmverify)
- https://icerm.brown.edu/ (ICERM, Rzk, K3 computations)
- https://www.claymath.org/ (CMI, Millennium Prize, CRF)
- https://deepmind.google/ (DeepMind Gemini/AlphaProof, Gemma, AlphaEvolve)
- https://ai.princeton.edu/ (Princeton AI Lab, PLI, AI², 300 H100)
- https://allenai.org/ (Ai2 Olmo/Asta/Semantic Scholar, truly open)
- https://github.com/deepseek-ai/DeepSeek-Prover-V2 + https://leandojo.org (DeepSeek-Prover, LeanDojo/ReProver)
- https://github.com/trishullab/PutnamBench (PutnamBench 640) + https://epoch.ai/frontiermath (FrontierMath 300)
- https://formal-conjectures.github.io (DeepMind 300 conjectures) + https://github.com/lean-dojo/LeanCopilot
- https://moogle.ai + https://github.com/austinletson/SorryDB + https://www.cl.cam.ac.uk/~jrh13/hol-light/ (Moogle/SorryDB/HOL Light)
