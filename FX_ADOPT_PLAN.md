# Adopt from fx — Simple Python Wins (no Zig)

*Scope: stay in Python. Pull only the genuinely simple, additive ideas from
`vercel-labs/fx` that we do NOT already have. Skip what's already here
(permissions/trust, sessions, MCP, skills, subagents, slash commands, themes,
prompts) and skip what's heavy (terminal render engine, wasm, ACP).*

## Already covered (don't re-port)
- Per-project trust with `ask/always/never` → `agent/project_trust.py`
- Sessions + resume/branch + JSONL, usage/cost → `session*.py`
- MCP server, slash commands, skills, subagents/workers, themes, prompts

## Candidate adoptions (ranked by simplicity × value)

### 1. Single settings file + one precedence rule  ★ simplest/highest value
fx: `env > ~/.fx/settings.json (workspace) > ~/.fx/settings.json (global) > .fx.json (project defaults) > built-in`. We scatter config across `env vars`, `~/.prover/models.json`, `tui.json`, `project trust`.
**Adopt:** introduce `~/.prover/settings.json` with a documented 5-level precedence, and read ALL of it (models, theme, permission-mode, defaults) through one tiny loader in `paths.py`.
*Result:* one place to look, one rule to remember.

### 2. Safe project-defaults file with a whitelist  ★simple
fx: project `.fx.json` accepts ONLY repo-safe keys (`sandbox`, `max_agent_steps`, `max_tool_result_bytes`, `context`) — credentials/model/permission are rejected before parsing.
**Adopt:** support committed `<repo>/.prover.json` carrying only our safe defaults (e.g. `{ "max_steps", "context_window" }`); ignore owned keys (`model`, `permission`, api keys). Click-through one-line helper that drops disallowed keys.
*Result:* a repo can pin sane defaults without leaking secrets.

### 3. Permission by tool with stable rule IDs (+ `/permissions`)  ★medium
fx: `/permissions remember allow|deny <tool> <args-json>` stores an exact rule under a stable ID; `/permissions list|revoke <id>`.
We have *per-project* trust but not *per-tool exact* rules with revocable IDs.
**Adopt:** add a small `permissions.py` ACL (tool name + optional arg-pattern → allow/deny, stable hash ID) + `/permissions list|revoke|remember`. Keep it independent of the project-trust modal.
*Result:* replace "always/never whole project" with precise, revocable tool rules.

### 4. Clean `ask` single-shot: JSON noninteractive, prompt→stderr  ★simple
fx: `fx ask "…"`; JSON/quiet stays noninteractive, Y/N prompt goes to stderr so stdout stays parseable.
**Adopt:** make `prover ask` default `--json` parseable, route approval/prompt text to stderr, add `--prompt-permissions` opt-in for a TTY Y/N.
*Result:* scriptable single theorem request without stdout noise.

### 5. Kebab-case flags + no-emojis + snake_case + minimal `pub`  ★trivial
Encode as a ruff/style policy + a one-line note in `AGENTS.md`/`CONTRIBUTING`.
*Result:* consistency, zero runtime cost.

### 6. "Run the real binary, not just tests" gate  ★process
Adopt fx AGENTS.md §1: before "done, report a crash-free end-to-end run of `prover` (not just `pytest`)".
*Result:* catches startup/render/thread bugs tests miss (especially in the TUI).

## Not adopting (deliberately)
- Zig rewrite, terminal render engine, wasm/ACP, web-search, git-publish, hooks/sounds — high effort, low value for a prover, or already out of scope.

## Order of implementation (if approved)
1. `#1 settings.json + precedence` (with `paths.py`) — smallest, biggest clarity win
2. `#2 .prover.json safe defaults`
3. `#3 permissions.py ACL + /permissions`
4. `#4 ask` single-shot clean-up
5. `#5` styling policy, `#6` process gate (docs/CI)

Each gated by: `ruff check agent/ tests/` → `pytest tests/` → manual `prover` run → commit.

---

## Implementation status — DONE (2026-08-21)

All six adoptions implemented in Python. **Zig rewrite dropped** (user decision).

| # | Deliverable | Files | Status |
|---|---|---|---|
| 1 | Layered settings + precedence | `agent/settings.py`, `tests/test_settings.py` | done |
| 2 | Repo-safe `.prover.json` whitelist | `agent/project_defaults.py`, `tests/test_project_defaults.py` | done |
| 3 | Per-tool ACL + `/permissions` | `agent/permissions.py`, `tests/test_permissions.py`, `/permissions` in `agent/commands.py` + `tests/test_commands.py` | done |
| 4 | `prover ask` clean single-shot | `agent/main.py` (+ `ask` subcommand) + `tests/test_main_usage.py` | done |
| 5 | Style policy | `AGENTS.md` | done |
| 6 | Process gate | `AGENTS.md` | done |

**Verification:** `ruff check agent/ tests/` clean; `pytest tests/` fast subset
437 passed. The slow LLM/Lean/LSP tests need a live endpoint (README notes the
configured HF endpoint hangs) and are excluded explicitly.

**Runtime integration — all wired (2026-08-21):**
- **MCP ACL enforcement** (`mcp.py`): every `tools/call` is gated through
  `PermissionStore.lookup()`; an explicit deny rule blocks the call with
  `isError`. Tools stay open by default, so the gate never breaks existing
  tooling. Verified end-to-end over real stdio (`prover mcp`).
- **TUI `/permissions`** (`tui.py`): `list` opens a modal; `remember` /
  `revoke` / `mode` act on the ACL store and persist. Verified headlessly.
- **Project defaults honored by the CLI** (`main.py`): `prover prove/bench/
  ask/leaderboard` and `--parallel` default to committed `max_steps`/`workers`;
  `quiet` suppresses `bench` progress. Exposed via a testable `_build_parser()`.
- `prover lean-baseline` happy path still exits 0 with clean stderr after the
  `cli()` refactor.

**Remaining (documented):** `settings.py` precedence is read only by
`project_defaults.effective_defaults()` (used by the CLI); the `PROVER_<KEY>`
env overrides in `agent/settings.py` are available for callers but not yet read
for every knob across `prover_loop.py`/`tui.py` — existing flags keep their
behaviour.
