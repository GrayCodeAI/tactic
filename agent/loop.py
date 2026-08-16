"""Core agent loop: draft → compile → parse errors → patch → repeat.

Architecture: the agent NEVER lets the model rewrite the whole file. We own
the theorem statement; the model only supplies the proof body (the tactics
after `:= by`). This makes "prove a different theorem" structurally
impossible — the statement is assembled by us, not the model.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import lean, llm

LEAN_DIR = Path(__file__).resolve().parent.parent / "lean"
TARGET = LEAN_DIR / "src" / "Tactic.lean"

# Prepended to every agent-written file so tactics/theorems are in scope.
HEADER = "import Mathlib\n\nopen BigOperators Nat Finset\n\n"

# One-shot "hammers" tried before spending any LLM tokens. Each costs one
# `lake build` (~3s) and solves a surprising fraction of problems outright.
HAMMERS = [
    "ring",
    "omega",
    "linarith",
    "nlinarith",
    "simp",
    "norm_num",
    "decide",
    "aesop",
    "tauto",
    "positivity",
]

SYSTEM = """You are an expert Lean 4 theorem prover.
You are given a theorem SIGNATURE (everything up to and including `:= by`)
and, after each attempt, the compiler diagnostics from `lake build`.
Respond with ONLY the tactic proof body — the lines that go after `:= by`,
indented two spaces, in a single ```lean code block. Rules:
- Do NOT restate, rename, or change the theorem. Only write the proof body.
- Do NOT include the theorem signature in your reply, only the tactics.
- Prefer hammers first: `ring`, `omega`, `linarith`, `nlinarith`, `simp`,
  `norm_num`, `positivity`, `aesop`. Only write manual induction/case
  analysis if hammers cannot close the goal.
- Use only core Lean 4 / Mathlib tactics available in the project.
- No `sorry`. The proof must fully type-check.
- If diagnostics are shown, fix exactly those errors."""


@dataclass
class Result:
    statement: str
    proved: bool
    steps: int
    seconds: float
    proof: str = ""
    history: list[str] = field(default_factory=list)


def _split_signature(statement: str) -> str:
    """Return the theorem signature up to and including `:= by`.

    Accepts statements given with or without a trailing proof.
    """
    s = statement.strip()
    m = re.search(r":=\s*by\b", s)
    if m:
        return s[: m.end()]
    # No `:= by` present — append it.
    return s + " := by"


def _extract_body(text: str) -> str:
    """Pull the proof body out of a model reply.

    Prefers a ```lean block; strips any accidental theorem signature lines.
    """
    code = llm.extract_lean_code(text)
    lines = []
    for ln in code.splitlines():
        stripped = ln.strip()
        # Skip anything that restates a theorem or re-imports.
        if re.match(r"^(theorem|lemma|example)\b", stripped):
            continue
        if re.match(r"^import\b", stripped):
            continue
        if re.match(r"^open\b", stripped):
            continue
        lines.append(ln)
    body = "\n".join(lines).strip("\n")
    # Normalize indentation to two spaces per tactic line.
    out = []
    for ln in body.splitlines():
        if not ln.strip():
            continue
        out.append("  " + ln.strip())
    return "\n".join(out)


def prove(statement: str, max_steps: int = 20, verbose: bool = True) -> Result:
    t0 = time.time()
    signature = _split_signature(statement)
    history: list[dict] = []

    def write_file(b: str) -> None:
        TARGET.write_text(HEADER + signature + "\n" + b + "\n")

    # ---- Hammer pre-pass: try one-shot tactics before spending LLM tokens.
    for i, hammer in enumerate(HAMMERS, 1):
        write_file(f"  {hammer}")
        ok, _ = lean.build(LEAN_DIR)
        if ok:
            final = TARGET.read_text()
            if verbose:
                print(f"  [hammer {i}/{len(HAMMERS)}] PROVED ∎ by `{hammer}`")
            return Result(statement, True, i, time.time() - t0, final, history)
    if verbose:
        print(f"  [hammer] no one-shot tactic worked, starting LLM loop")

    body = "  sorry"  # initial placeholder so the first build reports sorry
    write_file(body)

    for step in range(1, max_steps + 1):
        ok, output = lean.build(LEAN_DIR)
        if ok:
            final = TARGET.read_text()
            if verbose:
                print(f"  [step {step}] PROVED ∎")
            return Result(statement, True, step, time.time() - t0, final, history)

        report = lean.error_report(LEAN_DIR, output)
        if verbose:
            ndiag = len(lean.parse_diagnostics(output))
            tag = f"{ndiag} diagnostics" if ndiag else "sorry / not proved"
            print(f"  [step {step}] {tag}")

        user_msg = (
            f"Theorem signature:\n{signature}\n\n"
            f"Compiler diagnostics:\n{report}\n\n"
            "Write ONLY the tactic proof body."
        )
        history.append({"role": "user", "content": user_msg})
        reply = llm.chat(SYSTEM, history)
        if reply.startswith("[LLM error"):
            if verbose:
                print(f"  [step {step}] {reply}")
            history.append({"role": "assistant", "content": "(no response)"})
            continue
        new_body = _extract_body(reply)
        if new_body:
            body = new_body
            write_file(body)
            history.append({"role": "assistant", "content": reply})
        if len(history) > 12:
            history = history[-12:]

    return Result(statement, False, max_steps, time.time() - t0, "", history)
