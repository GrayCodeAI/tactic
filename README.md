# tactic

An agent that writes Lean 4 proofs. You give it a theorem; it iterates
(LLM draft → `lake` compile → parse diagnostics → fix) until the proof
type-checks. Ends with ∎

## Status

Scaffold. Core loop, error parsing, and benchmark harness in place.

## Setup

```bash
# 1. Lean toolchain + Mathlib (once; Mathlib fetch takes a while)
curl https://elan.lean-lang.org/elan-init.sh -sSf | sh
source ~/.bashrc
cd lean && lake update && lake exe cache get && lake build && cd ..

# 2. Python deps
pip install -e .

# 3. LLM access (any OpenAI-compatible endpoint)
export OPENAI_API_KEY=...          # or
export OPENAI_BASE_URL=http://localhost:11434/v1  # e.g. Ollama
export TACTIC_MODEL=gpt-4o
```

## Usage

```bash
# Prove a single theorem interactively (edits lean/src/Tactic.lean)
tactic prove "theorem pythagoras (a b c : ℕ) : a ^ 2 + b ^ 2 = c ^ 2 ↔ a = 0" --max-steps 20

# Interactive TUI: browse problems, watch live repairs (needs: pip install 'tactic[tui]')
tactic tui

# Run the benchmark (100 theorems, JSON in benchmark/problems.json)
tactic bench --max-steps 20 --report report.json
tactic bench --parallel 8            # isolation makes parallelism safe
tactic bench --no-goal-feedback      # errors only, no LSP goal state

# Local leaderboard: run a subset and record the score
tactic leaderboard --run --problems benchmark/trivial.json --name my-model
tactic leaderboard --show

# Use tactic from any MCP client (Claude, opencode, Cursor, …)
tactic mcp    # JSON-RPC tools: prove_theorem, benchmark_score, problems
```

## How it works

```
        ┌────────────┐
        │ statement  │
        └─────┬──────┘
              ▼
   ┌─────────────────────┐
   │ LLM drafts/patches  │◄──────────────┐
   │ the Lean proof      │               │
   └─────────┬───────────┘               │
             ▼                           │
        ┌─────────────┐   diagnostics    │
        │ lake build  │──────────────────┘
        └─────┬───────┘   (parsed, truncated,
              │            fed back to LLM)
              ▼  type-checks
           [PROVED ∎]
```

The whole trick is the error loop: Lean's compiler diagnostics are
machine-readable and precise, so the agent converges far better than
generate-and-hope.

## Layout

```
lean/           Lean 4 package (lake)
  src/Tactic.lean   target file the agent edits
  tmp/              per-problem files (benchmark isolation)
agent/          the agent (Python)
  loop.py         main iteration loop (+ hammer pre-pass)
  lean.py         lake invocation + diagnostic parsing
  llm.py          LLM provider (OpenAI-compatible) + cost tracking
  lsp.py          Lean language server client (goal-state feedback)
  mcp.py          MCP server (expose prove_theorem to any agent)
  tui.py          Textual TUI (browse problems, live proof trace)
  main.py         CLI (prove / bench / tui / mcp / leaderboard)
benchmark/      fixed theorem set + runner
leaderboard.json local score history (tactic leaderboard)
```

## Roadmap

- [x] 100-problem graded benchmark (benchmark/problems.json)
- [x] Better error-context extraction (surrounding source, not just line:col)
- [x] Per-problem Lean file isolation (parallel runs)
- [x] Proof trace logging + cost tracking
- [x] Goal-state feedback via Lean LSP (`getInteractiveGoals`)
- [x] MCP server wrapper (`tactic mcp`)
- [x] Leaderboard (local: `tactic leaderboard`; public site TBD)
- [ ] Public leaderboard + first results post
