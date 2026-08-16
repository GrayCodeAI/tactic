"""Core agent loop: draft → compile → parse errors → patch → repeat."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from . import lean, llm

LEAN_DIR = Path(__file__).resolve().parent.parent / "lean"
TARGET = LEAN_DIR / "src" / "Tactic.lean"

SYSTEM = """You are an expert Lean 4 theorem prover.
You will be given a theorem statement and, after each attempt, the compiler
diagnostics from `lake build`. Respond with the COMPLETE corrected Lean file
in a single ```lean code block. Rules:
- Keep the theorem name and statement exactly as given.
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


def prove(statement: str, max_steps: int = 20, verbose: bool = True) -> Result:
    t0 = time.time()
    TARGET.write_text(statement.strip() + "\n")
    history: list[dict] = []

    for step in range(1, max_steps + 1):
        ok, output = lean.build(LEAN_DIR)
        if ok:
            if verbose:
                print(f"  [step {step}] PROVED ∎")
            return Result(statement, True, step, time.time() - t0, TARGET.read_text(), history)

        report = lean.error_report(LEAN_DIR, output)
        if verbose:
            print(f"  [step {step}] {len(lean.parse_diagnostics(output))} diagnostics")

        history.append({"role": "user", "content": f"Compiler diagnostics:\n{report}"})
        reply = llm.chat(SYSTEM, history)
        code = llm.extract_lean_code(reply)
        if code:
            TARGET.write_text(code + "\n")
            history.append({"role": "assistant", "content": reply})
        # keep history bounded
        if len(history) > 12:
            history = history[-12:]

    return Result(statement, False, max_steps, time.time() - t0, "", history)
