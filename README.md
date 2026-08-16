# tactic

An agent that writes Lean 4 proofs. You give it a theorem; it iterates
(LLM draft → `lake` compile → parse diagnostics → fix) until the proof
type-checks. Ends with ∎

## Status

Scaffold. Core loop, error parsing, and benchmark harness in place.

## Setup

```bash
# 1. Lean toolchain (once)
curl https://elan.lean-lang.org/elan-init.sh -sSf | sh
source ~/.bashrc
lake --version

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

# Run the benchmark (100 theorems, JSON in benchmark/problems.json)
tactic bench --max-steps 20 --report report.json
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
agent/          the agent (Python)
  loop.py         main iteration loop
  lean.py         lake invocation + diagnostic parsing
  llm.py          LLM provider (OpenAI-compatible)
benchmark/      fixed theorem set + runner
```

## Roadmap

- [ ] Better error-context extraction (surrounding source, not just line:col)
- [ ] Per-problem Lean file isolation (parallel runs)
- [ ] Proof trace logging + cost tracking
- [ ] Public leaderboard
- [ ] MCP server wrapper
