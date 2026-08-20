"""Self-help documentation — Tau self_docs.py port (Tau 37a9e43 src/tau_coding/self_docs.py).

A compact help text surfaced by ``/help`` in the TUI and ``--help`` fallbacks.
"""

from __future__ import annotations

SELF_DOCS = """\
Lean Prover — Lean 4 proof agent

Proving a theorem
  /prove <theorem>     ask the repair loop to prove a Lean theorem
  /run                 run the benchmark suite interactively
  /board               open the leaderboard

Session control
  /new                 start a fresh session
  /resume [id]         resume a recorded session (/resume lists ids)
  /tree                show the session entry tree + pick a branch
  /fork [path]         fork the session at an entry (branch summary + fresh tail)
  /branch              re-run the proof from an earlier step with a summary
  /compact             force a context compaction now
  /export [html|jsonl|md]   export the session transcript

Model & settings
  /model [name]        show or switch the active model/provider
  /thinking [level]    off|minimal|low|medium|high|xhigh
  /login <provider>    sign in (openai-codex | anthropic | github-copilot)
  /logout <provider>   remove stored credentials

Context
  /usage               token/cost dashboard for the active session
  /stats               lifetime totals for the active session
  /skills              list discovered skills
  /contexts            list project context files
  /tools               list bound tools
  /help                this text"""


def help_text() -> str:
    return SELF_DOCS
