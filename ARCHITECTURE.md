# Architecture — Current & Proposed

A living map of lean-prover: what exists today, and a future-ready target that
keeps the working prover intact while removing the sharp edges (the two loop
files, the god-class TUI, the fat CLI dispatcher).

---

## 1. Current architecture (as of `38549ad`)

```
┌────────────────────────────────────────────────────────────────────────────┐
│                            CLI — agent/main.py                              │
│   _build_parser() → cli() → dispatch                                        │
│   prove · ask · bench · mcp · formalize · synth-data · lean-baseline        │
│   synth-lean · datagen · finetune · tui · login · update · version          │
│   rpc · chat · export · sessions · usage · leaderboard                      │
└──────────────┬──────────────────────┬─────────────────┬────────────────────┘
               │                      │                 │
        ┌──────▼─────┐          ┌─────▼─────┐     ┌─────▼──────┐
        │  TUI       │          │  MCP      │     │ ask /bench │
        │ tui.py ────│          │ mcp.py    │     │ /renderers │
        │ (2 280 LOC)│          │ (298 LOC) │     │            │
        └──────┬─────┘          └─────┬─────┘     └────────────┘
               │      slash/CommandResult   ACL gate (permissions.py)
               │              │             │
               ▼              ▼             ▼
        ┌───────────────────────────────────────────────┐
        │            PROOF ENGINE                        │
        │   prover_loop.py (739 LOC)  ·  loop.py (408)   │  ◄── TWO loops (hazard)
        │   prove() · prove_best_of() · hammer · adaptive │
        └──────┬──────────┬───────────────┬─────────┬────┘
               ▼          ▼               ▼         ▼
        ┌──────────┐ ┌─────────┐   ┌───────────┐ ┌──────────┐
        │ llm.py   │ │ lean.py │   │ lsp.py    │ │ tools.py │
        │ providers│ │ lake    │   │ goal state│ │ hammers  │
        │  + cost  │ │ compile │   │ runTactic │ │ baselines│
        └────┬─────┘ └─────────┘   └──────┬────┘ └──────────┘
             └───────────────┬────────────┘
                             ▼
              OpenAI-compatible /v1 · Lean toolchain (lake/Mathlib)

   Already-clean packages: session/  providers/  rendering/  extensions/
   fx-adopted layer (new): settings.py · project_defaults.py · permissions.py
```

**Today's sharp edges** (what the proposal targets):

| # | Problem | Location |
|---|---|---|
| 1 | Two overlapping loop files | `loop.py` + `prover_loop.py` |
| 2 | God-class TUI | `tui.py` 2 280 LOC |
| 3 | Fat CLI dispatcher | `main.py` 725 LOC |
| 4 | Engine called ad hoc by 8 modules | `coding_session`, `coding_tools`, `loop`, `main`, `rpc`, `system_prompt`, `tui_adapter`, `tui` |
| 5 | ACL gate only on MCP | `mcp.py` |

---

## 2. Proposed future-ready architecture

Principles: **one engine, many thin surfaces; boundaries over batteries; a
stable core API; ports-and-adapters for robustness.**

```
┌───────────────────────────  SURFACES (thin, swappable)  ────────────────────────┐
│  CLI       TUI (Textual)    MCP stdio    ACP (editors)   RPC    Batch / CI      │
│ cli/*.py   tui/app.py      mcp.py        acp/*.py        rpc.py  bench/*.py     │
│           + screens/handlers                                                      │
└──────┬───────────┬───────────────┬──────────────┬────────────┬───────────────────┘
       │           │               │              │            │
       ▼           ▼               ▼              ▼            ▼
┌────────────────────────────  CORE API (stable contract)  ───────────────────────┐
│   ProofSession · ProofResult · attempt · EventsStream                            │
│   prove()  prove_best_of()  hammer()  formalize()  plan()  bench()               │
└───────────────┬────────────────────────────┬─────────────────────────────────────┘
                │                            │
   ┌────────────▼─────────────┐   ┌──────────▼───────────────────────────────┐
   │   PROOF ENGINE (pure)    │   │   CONTROL LAYER (fx-adopted)              │
   │   engine/ — the single   │   │   settings   project_defaults             │
   │   repair loop + budgeting │   │   permissions (ACL gate ALL tools)        │
   │   NO I/O in the core     │   │   sessions/compaction/events              │
   └────────────┬─────────────┘   └────────────────────────────────────────────┘
                │            (depends on ports, not concrete adapters)
   ┌────────────▼───────────────  INFRA / ADAPTERS (behind ports)  ──────────┐
   │  LLMClient   LeanRunner   LSPClient   Retriever   Tools   CostEstimator │
   │  providers/  lean.py      lsp.py      retrieval   tools.py llm.cost     │
   │  context_window · models · session/* · skills                           │
   └──────────────┬──────────────────────────────────────────────────────────┘
                  ▼
        OpenAI-compatible · Lean toolchain (lake/Mathlib) · providers fleet

```

---

## 3. What changes — with priority

| Step | Change | Priority | Risk |
|---|---|---|---|
| A | **Unify loops**: one `engine/` `ProofEngine`; delete/alias `loop.py`; single `attempts`/`Result` shape | High | Medium |
| B | **Extract TUI** into `tui/` package (`app.py`, `screens/`, `handlers/`); thin core-API calls | High | Medium-High |
| C | **Extend ACL gate** beyond MCP to local/TUI sensitive tools | High | Low |
| D | **Core API as the only entry**: surfaces call `engine.api.*`, never internals | High | Medium |
| E | **Ports & adapters**: `LLMClient`/`LeanRunner`/`LSPClient` interfaces (enables fakes/stubs for tests, provider swap) | Medium | Medium |
| F | **Robustness**: retry+backoff with jitter, per-attempt cancellation, transactional session recovery (WAL), structured telemetry sink behind a port | Medium | Medium |
| G | **Embeddability**: add ACP server; optional wasm via thin adapter (reuse today's `providers/` + pure engine) | Low (optional) | Medium |
| H | **CLI→`cli/` registry**: thin command modules, remove god-dispatcher | Low | Low-Medium |

Priority order is **A → D → C → E → F → B → H**; G only if embeddability is a
stated goal. A/D give the biggest maintainability win with the least churn;
C is a quick security win; B/H are cosmetic-but-worthwhile; G is truly optional.

---

## 4. Robustness details (what "robust" concretely adds)

- **Pure core**: the engine holds no I/O — all effects go through injected ports,
  so tests can drive the whole loop with fakes (no endpoint/LSP needed).
- **Retry & backoff**: exponential backoff + jitter on provider/transport errors
  (extends today's thin `provider_retry.py`).
- **Cancellation**: per-attempt cancel tokens; surfaces can stop cleanly.
- **Transactional sessions**: write-ahead append (already JSONL) + startup
  recovery for interrupted runs (extends `session_manager.py`/`session/storage.py`).
- **Observability**: everything already flows through the single `events.py`
  emit path — add a telemetry sink behind a port so TUI/JSON/`/usage` stay in sync
  without touching the engine.

## 5. Non-goals (kept out on purpose)

- No rewrite of the Lean toolchain / Mathlib — we keep wrapping `lake`/Mathlib.
- No forcing every knob through `settings.py` — domain-specific resolution
  (model profiles, family context tables) stays where it owns the semantics.
- No Zig / no framework churn.

## 6. Suggested first move

Start with **steps A + D** (unify `proof_loop`/`loop` into `engine/` and make
surfaces call only the stable API). It is the highest-ROI change and unlocks
C/E/F cleanly. Steps C (ACL everywhere) is a quick, low-risk add-on.
