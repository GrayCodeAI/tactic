"""Core agent loop: draft → compile → parse errors → patch → repeat.

Architecture: the agent NEVER lets the model rewrite the whole file. We own
the theorem statement; the model only supplies the proof body (the tactics
after `:= by`). This makes "prove a different theorem" structurally
impossible — the statement is assembled by us, not the model.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from . import lean, llm, lsp

LEAN_DIR = Path(__file__).resolve().parent.parent / "lean"

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
- If OPEN GOALS are shown, your proof must close every one.
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
    # Token/cost tracking
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    # Proof trace
    trace: list[dict] = field(default_factory=list)
    # True when the run was aborted by should_stop (e.g. TUI Stop)
    stopped: bool = False


def _get_lean_file(problem_id: str | None = None) -> Path:
    """Get a unique Lean file for this problem. Uses lean/tmp/ for isolation."""
    if problem_id:
        tmp_dir = LEAN_DIR / "tmp"
        tmp_dir.mkdir(exist_ok=True)
        return tmp_dir / f"Tactic_{problem_id}.lean"
    # Fallback to original single file (for `prove` command)
    return LEAN_DIR / "src" / "Tactic.lean"


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


def prove(
    statement: str,
    max_steps: int = 20,
    verbose: bool = True,
    problem_id: str | None = None,
    goal_feedback: bool = True,
    on_event: Callable[[dict], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> Result:
    t0 = time.time()
    signature = _split_signature(statement)
    history: list[dict] = []
    trace: list[dict] = []
    total_prompt = 0
    total_completion = 0
    total_tokens = 0

    def emit(event: dict) -> None:
        if on_event:
            on_event(event)

    def stop_requested() -> bool:
        return bool(should_stop and should_stop())

    target_file = _get_lean_file(problem_id)

    def write_file(b: str) -> None:
        target_file.write_text(HEADER + signature + "\n" + b + "\n")

    def check_file() -> tuple[bool, str]:
        """Run `lean --check` on the target file for fast, isolated verification."""
        return lean.check_file(target_file, LEAN_DIR)

    # LSP session for goal-state feedback (lazily started, may stay None).
    lsp_client: lsp.LeanLSP | None = None

    def get_goals(current_text: str) -> str | None:
        """Open goal state via LSP. Returns formatted goals or None."""
        nonlocal lsp_client
        if not goal_feedback:
            return None
        if lsp_client is None:
            lsp_client = lsp.LeanLSP(LEAN_DIR, target_file)
        try:
            lsp_client.update(current_text)
            goals = lsp_client.goal_at_end(current_text)
            return goals
        except Exception:  # noqa: BLE001 — LSP feedback is optional; never break the loop
            return None

    # ---- Hammer pre-pass: try one-shot tactics before spending LLM tokens.
    for i, hammer in enumerate(HAMMERS, 1):
        if stop_requested():
            break
        write_file(f"  {hammer}")
        emit({"type": "hammer", "i": i, "total": len(HAMMERS), "tactic": hammer})
        ok, output = check_file()
        trace.append({"step": i, "type": "hammer", "tactic": hammer, "ok": ok, "output": output[-500:] if not ok else ""})
        if ok:
            final = target_file.read_text()
            emit({"type": "proved", "how": f"hammer:{hammer}", "steps": i})
            if verbose:
                print(f"  [hammer {i}/{len(HAMMERS)}] PROVED ∎ by `{hammer}`")
            if lsp_client:
                lsp_client.close()
            return Result(
                statement, True, i, time.time() - t0, final, history,
                total_prompt, total_completion, total_tokens, 0.0, trace
            )
    emit({"type": "llm_start"})
    if verbose:
        print("  [hammer] no one-shot tactic worked, starting LLM loop")

    body = "  sorry"  # initial placeholder so the first build reports sorry
    write_file(body)

    for step in range(1, max_steps + 1):
        if stop_requested():
            emit({"type": "stopped"})
            cost = llm.estimate_cost(total_prompt, total_completion)
            if lsp_client:
                lsp_client.close()
            return Result(
                statement, False, step - 1, time.time() - t0, "", history,
                total_prompt, total_completion, total_tokens, cost, trace, True
            )
        ok, output = check_file()
        diags = lean.parse_diagnostics(output)
        ndiag = len(diags)
        trace.append({"step": step, "type": "build", "ok": ok, "diagnostics": ndiag, "output_tail": output[-500:]})
        if ok:
            final = target_file.read_text()
            emit({"type": "proved", "how": "llm", "steps": step})
            if verbose:
                print(f"  [step {step}] PROVED ∎")
            cost = llm.estimate_cost(total_prompt, total_completion)
            if lsp_client:
                lsp_client.close()
            return Result(
                statement, True, step, time.time() - t0, final, history,
                total_prompt, total_completion, total_tokens, cost, trace
            )

        report = lean.error_report(LEAN_DIR, output)
        emit({"type": "build", "step": step, "ok": False, "diagnostics": ndiag,
              "summary": (diags[0].message if diags else "sorry / not proved")})
        goals = get_goals(HEADER + signature + "\n" + body + "\n")
        if goals:
            trace.append({"step": step, "type": "goal", "goals": goals})
            emit({"type": "goals", "step": step, "goals": goals})
        if verbose:
            tag = f"{ndiag} diagnostics" if ndiag else "sorry / not proved"
            if goals:
                tag += " + goals"
            print(f"  [step {step}] {tag}")

        user_msg = (
            f"Theorem signature:\n{signature}\n\n"
            f"Compiler diagnostics:\n{report}\n\n"
            + (f"Open goals at the end of your last proof attempt:\n{goals}\n\n" if goals else "")
            + "Write ONLY the tactic proof body."
        )
        history.append({"role": "user", "content": user_msg})
        emit({"type": "llm_request", "step": step})
        resp = llm.chat(SYSTEM, history)
        if resp.content.startswith("[LLM error"):
            emit({"type": "llm_error", "step": step, "error": resp.content})
            if verbose:
                print(f"  [step {step}] {resp.content}")
            history.append({"role": "assistant", "content": "(no response)"})
            trace.append({"step": step, "type": "llm", "error": resp.content})
            continue
        new_body = _extract_body(resp.content)
        if new_body:
            body = new_body
            write_file(body)
            history.append({"role": "assistant", "content": resp.content})
        total_prompt += resp.prompt_tokens
        total_completion += resp.completion_tokens
        total_tokens += resp.total_tokens
        emit({"type": "llm_response", "step": step,
              "tokens": resp.total_tokens, "body": new_body or "(empty)"})
        trace.append({"step": step, "type": "llm", "prompt_tokens": resp.prompt_tokens, "completion_tokens": resp.completion_tokens, "body": new_body[:200]})
        if len(history) > 12:
            history = history[-12:]

    emit({"type": "failed", "max_steps": max_steps})
    cost = llm.estimate_cost(total_prompt, total_completion)
    if lsp_client:
        lsp_client.close()
    return Result(
        statement, False, max_steps, time.time() - t0, "", history,
        total_prompt, total_completion, total_tokens, cost, trace
    )
