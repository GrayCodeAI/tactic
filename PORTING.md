# Tactic ← Tau Porting Plan

Full port plan for the remaining huggingface/tau (HEAD `aec16bb`) surface.
Completed ports are checked off; every port follows the same gate:
`ruff check agent/ tests/` → full `pytest tests/` (currently 279) → commit + push.

Reference clone: `/tmp/opencode/tau` (git pull before each item).

---

## Batch 4 — Core port remainder — **DONE**

### 4.1 [x] `agent/paths.py` — central config paths (tau `paths.py`, 130 lines)

**Goal**: single source of truth for all user/project dirs; kill scattered env reads.

Port `TauPaths` as `TacticPaths` (frozen dataclass, `home` default `~/.tactic`,
`agents_home` `~/.agents`):
- `sessions_dir`, `config_dir`, `prompts_dir` (user-level), `themes_dir`, `logs_dir`
- Env override contract (existing vars win, else default, else `TACTIC_CONFIG_DIR`):
  `TACTIC_SESSIONS_DIR`, `TACTIC_PROMPTS_DIR`, `TACTIC_CONFIG_DIR` (already honored
  by project_trust) + new `TACTIC_THEMES_DIR`, `TACTIC_LOGS_DIR`
- Repo-root discovery: `<CWD>/.tactic/prompts`, `<CWD>/.tactic/themes`
  (project dirs win over user dirs — current prompt_templates behavior stays)

**Files**: new `agent/paths.py`; refactor `session_manager.py`, `prompt_templates.py`,
`themes.py`, `project_trust.py`, `tui.py`, `main.py` to consume it (no behavior change).

**Tests**: `tests/test_paths.py` — env overrides, project-over-user precedence,
`TACTIC_CONFIG_DIR` fallback.

**Acceptance**: no `Path.home()`/`getenv` dir plumbing outside `paths.py`; full suite green.

---

### 4.2 [x] `agent/context_window.py` — token-based context accounting (tau `context_window.py`, 353)

**Goal**: replace char-based budgets with token estimates (≈4 chars/token heuristic,
tau parity), used by compaction + branch summaries.

Port:
- `estimate_text_tokens(text)`, `estimate_message_tokens(message)` (adapted from
  tau's `AgentMessage` to tactic's dict history items)
- `estimate_context_tokens(...)`
- `auto_compaction_threshold_for_context_window(tokens)` → 70% of `llm.llm`'s
  known context window (constant in `llm.py`; make it env-tunable
  `TACTIC_CONTEXT_WINDOW`)
- `summarize_messages_for_compaction` / `build_compaction_summary_prompt` /
  `serialize_messages_for_compaction` (tau's shapes) — adapt into current
  `agent/compaction.py` while keeping its event-record behavior

**Files**: new `agent/context_window.py`; touch `compaction.py`,
`branch_summary.py` (swap `MAX_SUMMARY_SOURCE_TOTAL_CHARS` for a token budget),
loop history trimming.

**Tests**: `tests/test_context_window.py` — token estimate sanity (whitespace,
code blocks), threshold math, compaction round-trip with existing record fixtures.

**Acceptance**: compaction triggers on 70% window instead of fixed turns;
branch summary budget in tokens; suite green.

---

### 4.3 [x] `agent/session_usage.py` — per-session cost dashboard (tau `session_usage.py`, 920)

**Goal**: tau's `/usage`-style accounting: aggregate tokens + estimated cost per
session and across all sessions, with an ASCII dashboard.

Port:
- `RequestUsage`, `UsageEvent`, `SessionUsage` dataclasses
- `collect_session_usage(entries)` — feed it tactic `SessionEntry`/index rows or
  raw records (records already carry `prompt_tokens`/`completion_tokens`/
  `tokens`; `session_stats.py` counters stay as the per-session source)
- `estimated_request_cost` with tactic's pricing constants (`$0/M` — keep the
  existing cost columns in `session_stats.py` as source of truth)
- `render_usage_dashboard` (ASCII line chart, color pairs, compact numbers)
- New command `/usage`: session picker → dashboard for one session OR `/usage all`
  → across sessions; **files**: `agent/commands.py` (registry 21 → 22),
  `agent/tui.py` (render into a screen), `agent/main.py` (`tactic usage` CLI)

**Files**: new `agent/session_usage.py`; `commands.py`, `tui.py`, `main.py`.

**Tests**: `tests/test_session_usage.py` — aggregation math, empty/missing-token
records, dashboard rendering smoke (headers/rows), `/usage` command registered
and TUI action wired.

**Acceptance**: `tactic usage` prints per-session tokens/$ and dashboard;
suite green.

---

### 4.4 [x] `/reload` output summary (tau `reload.py`, 31 lines)

**Goal**: parity with `CodingReloadSummary` — `/reload` logs before/after counts.

Port: `ReloadCategorySummary` (before/after/changed/delta) + `CodingReloadSummary`
shape adapted to tactic categories: `problems`, `themes`, `prompt_templates`,
`trust` (state persisted), `system_prompt_rebuilt`.

**Files**: new `agent/reload.py` (or fold into `tui.py`); `_reload_resources()`
collects pre/post counts and logs the summary line.

**Tests**: extend `tests/test_tui_reload.py` (or the trust TUI tests) — one
assertion on the logged summary text.

**Acceptance**: `/reload` prints `problems 12→15 (+3) · themes 2→2 · prompts 4→4`-style
line; suite green.

---

## Batch 5 — Integration polish — **DONE**

### 5.1 [x] Usage in session index + `tactic sessions`
- Add `cost`/`tokens` columns populated from record aggregates (`collect_session_usage`
  over each session's records) to the sessions index rendering in `main.py`.

### 5.2 [x] Auto-compaction threshold wiring
- `loop.py` computes `auto_compaction_threshold_for_context_window` once per run;
  feed the resulting budget into the compaction trigger and history trimming.

### 5.3 [x] Doc sweep
- `PORTING.md` checkoffs; `GUIDE.md`: `/usage` command, `/reload` summary format,
  `TACTIC_CONTEXT_WINDOW`; `README.md` roadmap + test count; new env vars table.

---

## Batch 6 — Remaining tau surfaces — **DONE**

### 6.1 [x] `agent/thinking.py` (tau `thinking.py`, 90 lines)
- Thinking levels (`off`..`xhigh`), `normalize_thinking_level(s)`,
  `reasoning_effort_for_level`, `anthropic_thinking_budget_for_level`,
  `next_thinking_level` (cycle).
- Tactic default is `off` (tau's is `medium`): proofs repair fastest with no
  thinking; the compile loop is the signal. `TACTIC_THINKING` sets a level,
  `TACTIC_DISABLE_THINKING=1` stays the hard off-switch, explicit level wins.
- Wired into `llm._call`: off → vLLM/HF `enable_thinking: False` switch
  (previous behavior); non-off → OpenAI `reasoning_effort`.
- Tests: `tests/test_thinking.py`, `tests/test_llm_thinking.py`.

### 6.2 [x] `agent/diagnostics.py` (tau `diagnostics.py`, 163 lines)
- `ProofCallDiagnosticContext` / `ProofCallDiagnosticLogger`
  (tau `AgentCallDiagnosticContext` / `AgentCallDiagnosticLogger`),
  `new_proof_call_run_id`. JSONL under `TacticPaths.logs_dir`
  (`~/.tactic/logs/agent-calls.jsonl`) — now the first real consumer
  of `logs_dir`.
- `log_exception` (traceback) + `log_llm_error` (status/attempts extraction).
  Writes are best-effort: diagnostics never break the proof loop.
- Wired into `loop.prove()` at the `llm_error` emit site.
- Tests: `tests/test_diagnostics.py`, `tests/test_loop_diagnostics.py`.

### 6.3 [x] `agent/rendering.py` (tau `rendering/` package, ~213 lines)
- `PrintOutputMode` (`text`/`json`/`transcript`), `EventRenderer` protocol,
  `JsonEventRenderer`, `FinalTextRenderer`, `TranscriptRenderer`,
  `create_event_renderer` — adapted from tau's typed event objects to
  tactic's dict event records (`agent/events.py`).
- Wired into `main.cmd_prove --output {text,json,transcript}` (tau's print
  modes; `text` keeps the classic summary, `--output transcript/json` streams).
- Tests: `tests/test_rendering.py`.

### 6.4 [x] `tactic usage` CLI (Batch 4.3 acceptance completion)
- `main.cmd_usage`: `tactic usage [session-id|all]` renders the
  `session_usage` dashboard (single session or aggregate across sessions),
  mirroring the `/usage` TUI command.
- Tests: `tests/test_main_usage.py`.

---

## Explicitly skipped (documented, do not vendor)

| tau surface | reason |
|---|---|
| `tools.py` (1215), `skills.py`, `catalog_loader.py`, `resources.py`, `extensions/` | no Lean file-mutation mapping; tool = Lean server |
| `oauth_*`, `provider_*`, `credentials.py`, `tau_ai/*` | single OpenAI-compatible endpoint; env-auth |
| `system_prompt.py` | tactic's loop prompt is benchmark-tuned (68/100) |
| `updater.py`, `update_check.py`, `self_docs.py`, `version.py` | packaged tool, no self-update pipeline |
| `image_processing.py`, `shell_config.py` | no images / no shell in proof loop |
| `cli.py` | already covered by `main.py` |
| tau `session.py` continuations (#591/#592) | tool-edit-only features |
| `context.py` (AGENTS.md project-instruction discovery) | tactic's system prompt is fixed by the loop; no instruction-file contract |
| `tui/config.py` `tui/state.py` `tui/adapter.py` | tactic's `tui.py` is a single-file rewrite on tactic events; tau's state/adapter model typed events with no counterpart |
| tau `rendering` typer/rich console styling + `CustomMessageMarkup` | tactic print path is plain ANSI via `events.format()`; no extension API |
| `tui/widgets.py` `tui/app.py` (11.5k lines) | Textual rewrite lives in tactic `tui.py` (proof-specific panels, not chat widgets) |

---

## Gate checklist (every batch)

1. `git pull` in `/tmp/opencode/tau` (parity with HEAD)
2. Port + lint: `ruff check agent/ tests/`
3. Full suite: `pytest tests/` (209 → goal ≥ 220)
4. Commit + push `main`
5. Update `PORTING.md` checkoffs + docs in the same commit