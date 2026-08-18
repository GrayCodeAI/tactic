# tactic

An agent that writes Lean 4 proofs. You give it a theorem; it iterates
(LLM draft → `lake` compile → parse diagnostics → fix) until the proof
type-checks. Ends with ∎

## Status

Working agent, 100-problem benchmark, interactive TUI, MCP server,
session resume/branching, history compaction, theming.
Current best: **Qwen3.8-27B on Mathlib v4.20.0 scores 68/100**
(trivial 20/20, easy 23/30, medium 21/30, hard 4/20), $0 cost (free HF endpoint).

## Setup

```bash
# 1. Lean toolchain + Mathlib (once; Mathlib fetch takes a while)
curl https://elan.lean-lang.org/elan-init.sh -sSf | sh
source ~/.bashrc
cd lean && lake update && lake exe cache get && lake build && cd ..

# 2. Python deps
pip install -e .
pip install textual pyperclip   # for the TUI + clipboard
pip install pytest              # to run the test suite

# 3. LLM access (any OpenAI-compatible endpoint)
export OPENAI_API_KEY=...          # or
export OPENAI_BASE_URL=http://localhost:11434/v1  # e.g. Ollama
export TACTIC_MODEL=gpt-4o
```

### Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `OPENAI_API_KEY` / `OPENAI_BASE_URL` | — | Any OpenAI-compatible provider. |
| `TACTIC_MODEL` | `gpt-4o` | Model name for `/status` + cost lookup. |
| `TACTIC_CONTEXT_WINDOW` | per-model table in `llm.py` | Override the context-window size used to compute the auto-compaction budget. |
| `TACTIC_SESSIONS_DIR` | `~/.tactic/sessions` | Where proof sessions (JSONL) are recorded. |
| `TACTIC_PROMPTS_DIR` | `~/.tactic/prompts` (or `$TACTIC_CONFIG_DIR/prompts`) | User-level prompt templates (project `<repo>/.tactic/prompts` wins). |
| `TACTIC_THEMES_DIR` | `~/.tactic/themes` | Custom TUI themes (`*.json`). |
| `TACTIC_LOGS_DIR` | `~/.tactic/logs` | Diagnostic logs. |
| `TACTIC_CONFIG_DIR` | `~/.tactic` | Overrides the whole user config home (prompts/themes/logs/trust). |
| `TACTIC_TRUST` | `always` | Project trust policy: `always` / `never` / `ask`. |
| `TACTIC_NO_SESSIONS` | `0` | `1` disables session recording. |
| `TACTIC_BRANCH_SUMMARY` | `1` | `0` disables model-assisted branch summaries. |
| `TACTIC_THINKING` | unset (`off`) | Reasoning level: `off`/`minimal`/`low`/`medium`/`high`/`xhigh`. Non-`off` sends OpenAI `reasoning_effort`. |
| `TACTIC_DISABLE_THINKING` | `1` | Hard thinking off-switch (vLLM/HF `enable_thinking: False`); an explicit `TACTIC_THINKING` wins. |
| `TACTIC_LLM_TIMEOUT` | `180` | Hard wall-clock cap (seconds) per LLM call. |

## Usage

```bash
# Prove a single theorem interactively (edits lean/src/Tactic.lean)
tactic prove "theorem pythagoras (a b c : ℕ) : a ^ 2 + b ^ 2 = c ^ 2 ↔ a = 0" --max-steps 20

# Interactive TUI: browse problems, watch live repairs, slash commands
tactic tui            # or: tactic tui -p 4 (parallel workers)

# Slash commands inside the TUI prompt bar (Tab-less: ctrl+space completes):
#   /help /prove /run /stop /workers <n> /resume <id> /branch <id> [turn]
#   /export <path> /theme [name] /status /model /system /hotkeys /clear /quit
#   /usage [session-id|all] /reload

# Run the benchmark (100 theorems, JSON in benchmark/problems.json)
tactic bench --max-steps 20 --report report.json
tactic bench --parallel 4            # isolation makes parallelism safe
tactic bench --no-goal-feedback      # errors only, no LSP goal state
tactic bench --no-record             # skip JSONL session logs

# Inspect recorded proof sessions (event stream per run)
tactic sessions                      # list recent sessions
tactic sessions 20260817-015954-proof       # replay one
tactic sessions 20260817-015954-proof --raw # with raw JSON records

# Token/cost dashboard (per session or across all)
tactic usage                         # all sessions
tactic usage 20260817-015954-proof   # one session

# Machine-readable proof output
tactic prove "..." --output json         # one JSON event per line
tactic prove "..." --output transcript   # colored step transcript

# Local leaderboard: run a subset and record the score
tactic leaderboard --run --problems benchmark/trivial.json --name my-model
tactic leaderboard --show

# Use tactic from any MCP client (Claude, opencode, Cursor, …)
tactic mcp    # JSON-RPC tools: prove_theorem, benchmark_score, problems

# Tests
pytest tests/        # ~272 tests (loop, compaction, session, TUI, commands)
```

## How it works

```
        ┌────────────┐
        │ statement  │
        └─────┬──────┘
              ▼
   ┌─────────────────────┐
   │ hammer pre-pass     │  ring / omega / linarith / simp / …
   │ (before any LLM)    │  → most easy problems stop here
   └─────────┬───────────┘
             ▼ (no hammer worked)
   ┌─────────────────────┐
   │ LLM drafts/patches  │◄──────────────┐
   │ the proof body      │               │
   └─────────┬───────────┘               │
             ▼                           │
        ┌─────────────┐   diagnostics    │
        │ lake env    │   + goal state   │
        │ lean --check│──────────────────┘
        └─────┬───────┘   (LSP RPC, source context)
              ▼  type-checks
           [PROVED ∎]
```

The model only ever supplies the proof body — the theorem statement is
assembled by us, so "prove a different theorem" is structurally
impossible. History is compacted (old attempts folded into a failed-attempts
summary) rather than truncated, so weak models stop re-trying dead ends.

## Layout

```
lean/               Lean 4 package (lake), Mathlib pinned to v4.20.0
  src/Tactic.lean   target file the agent edits
  tmp/              per-problem files (benchmark isolation)
agent/              the agent (Python)
  loop.py           repair loop + hammer pre-pass + resume/branch
  events.py         event protocol — one stream to trace/session/TUI
  session.py        JSONL sessions (~/.tactic/sessions/)
  session_manager.py index.jsonl upsert/list + history rebuild
  session_stats.py  per-session token + cost aggregation
  compaction.py     failed-attempts summary (tau's memory model)
  lean.py           lake invocation + diagnostic parsing
  llm.py            LLM provider (OpenAI-compatible) + cost tracking
  lsp.py            Lean language server client (goal-state feedback)
  mcp.py            MCP server (expose prove_theorem to any agent)
  commands.py       slash-command registry (tau pattern, 22 built-ins)
  paths.py          canonical user/project dir config (env overrides)
  context_window.py token-based context estimation + auto-compaction threshold
  session_usage.py  /usage token + cost dashboard
  thinking.py       reasoning levels → provider kwargs (tau thinking port)
  diagnostics.py    structured JSONL failure log (~/.tactic/logs/, tau port)
  rendering.py      --output text/json/transcript renderers (tau rendering port)
  autocomplete.py   slash-command completions (tau pattern)
  themes.py         TUI themes as JSON data (tau pattern)
  terminal_title.py OSC terminal title + braille spinner (tau pattern)
  tui.py            Textual TUI (problems, live trace, replay, commands)
  main.py           CLI (prove / bench / tui / mcp / sessions / usage / leaderboard)
benchmark/          fixed theorem set + runner + merge_reports.py
tests/              pytest suite (272 tests)
leaderboard.json    local score history (tactic leaderboard)
```

## Roadmap

- [x] 100-problem graded benchmark (benchmark/problems.json)
- [x] Better error-context extraction (surrounding source, not just line:col)
- [x] Per-problem Lean file isolation (parallel runs)
- [x] Proof trace logging + cost tracking
- [x] Goal-state feedback via Lean LSP (`getInteractiveGoals`)
- [x] MCP server wrapper (`tactic mcp`)
- [x] Leaderboard (local: `tactic leaderboard`; public site TBD)
- [x] TUI: custom prove, session replay, parallel workers, Errors panel
- [x] Clipboard (tau port: pyperclip + OSC-52 fallback, selection-aware)
- [x] Slash commands + completions (tau pattern, 21 built-ins) + ctrl+k palette
- [x] Session resume + branching (`/branch <session> [turn]`, model branch summaries)
- [x] File drops into the prompt bar (paths quoted/URI-decoded, tau port)
- [x] Session export (`/export`, JSONL + self-contained HTML transcript)
- [x] Project trust gating (`.tactic` protected resources, modal + env policy)
- [x] Prompt templates (`/prompts` picker, slash expansion, project override)
- [x] History compaction (failed-attempts summary) + token-based auto-compaction
- [x] Themes + terminal-title chrome + OSC 9/99 completion notification (tau pattern)
- [x] Queued prompts while running (ctrl+e to edit), /new /compact /name (tau pattern)
- [x] Session token + cost dashboard (`/usage`, per-session and across all)
- [x] `/reload` resource change summary (problems/themes/prompts before→after)
- [x] Thinking levels, structured failure log, `--output` renderers, `tactic usage` CLI (tau port)
- [x] Results post + public leaderboard (see leaderboard.json)
- [ ] Public leaderboard site (submissions welcome via PR)
