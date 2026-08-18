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

from . import events, lean, llm, lsp
from .compaction import compact_history
from .context_window import (
    auto_compaction_threshold_for_context_window,
    estimate_context_tokens,
)
from .diagnostics import (
    ProofCallDiagnosticContext,
    ProofCallDiagnosticLogger,
    new_proof_call_run_id,
)
from .session import Session, read_session
from .session_manager import SessionManager, SessionRecord, history_from_records

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
    # Proof trace (event records — see agent/events.py)
    trace: list[dict] = field(default_factory=list)
    # True when the run was aborted by should_stop (e.g. TUI Stop)
    stopped: bool = False
    # JSONL session log for this run (None if recording disabled)
    session_path: str | None = None


def _get_lean_file(problem_id: str | None = None) -> Path:
    """Get a unique Lean file for this problem. Uses lean/tmp/ for isolation."""
    if problem_id:
        tmp_dir = LEAN_DIR / "tmp"
        tmp_dir.mkdir(exist_ok=True)
        return tmp_dir / f"Prover_{problem_id}.lean"
    # Fallback to original single file (for `prove` command)
    return LEAN_DIR / "src" / "Prover.lean"


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
    record_session: bool = True,
    resume_from: str | None = None,
    branch_at: int | None = None,
    branch_summary: str | None = None,
    skip_hammers: bool = False,
) -> Result:
    t0 = time.time()
    signature = _split_signature(statement)
    history: list[dict] = []
    trace: list[dict] = []
    total_prompt = 0
    total_completion = 0
    total_tokens = 0

    session = Session(problem_id=problem_id)
    session_open = session.open() if record_session else False
    session_path = str(session.path) if session_open else None
    manager = SessionManager()

    # Structured failure log (tau AgentCallDiagnosticLogger parity): machine-
    # readable JSONL of LLM failures under the paths logs_dir, alongside the
    # human-readable llm_error event stream.
    diag = ProofCallDiagnosticLogger.from_paths()
    diag_context = ProofCallDiagnosticContext(
        model=llm.model(),
        cwd=LEAN_DIR,
        session_id=session.id,
        run_id=new_proof_call_run_id(),
        problem_id=problem_id,
    )

    def emit(event: str, **payload) -> None:
        """Single emit path: trace + session JSONL + callback + CLI print."""
        rec = events.record(event, **payload)
        trace.append(rec)
        session.write(rec)
        if on_event:
            on_event(rec)
        if verbose:
            line = events.format(rec)
            if line:
                print(line)

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

    def finish(
        proved: bool, steps: int, proof: str, cost: float, stopped: bool = False
    ) -> Result:
        secs = time.time() - t0
        if lsp_client:
            lsp_client.close()
        emit(
            "result",
            proved=proved,
            steps=steps,
            seconds=round(secs, 2),
            prompt_tokens=total_prompt,
            completion_tokens=total_completion,
            total_tokens=total_tokens,
            cost_usd=cost,
            stopped=stopped,
            session_id=session.id if session_open else None,
        )
        session.close()
        if record_session:
            manager.upsert(SessionRecord(
                id=session.id, path=str(session.path), problem_id=problem_id,
                model=llm.model(),
                status="stopped" if stopped else ("proved" if proved else "failed"),
                proved=proved, steps=steps,
                created_at=t0, updated_at=time.time(),
            ))
        return Result(
            statement, proved, steps, secs, proof, history,
            total_prompt, total_completion, total_tokens, cost, trace,
            stopped, session_path,
        )

    emit("start", statement=statement, problem_id=problem_id,
         max_steps=max_steps, model=llm.model())
    if record_session:
        manager.upsert(SessionRecord(
            id=session.id, path=str(session.path), problem_id=problem_id,
            model=llm.model(), status="running",
            created_at=t0, updated_at=time.time(),
        ))

    # ---- Resume/branch: seed the repair history from a recorded session
    # (tau: replay the root→leaf path to rebuild harness messages).
    body = None  # initial proof body; seeded on resume
    if resume_from:
        records = []
        for rec in manager.list_sessions():
            if rec.id == resume_from:
                records = read_session(Path(rec.path))
                break
        if records:
            seed = history_from_records(records)
            if branch_at is not None:
                # branch_at = keep only the first N user/assistant turns,
                # discarding the rest of the recorded trajectory
                # (tau: repoint the LeafEntry at an earlier entry).
                seed = seed[: max(0, branch_at) * 2]
            if seed:
                history = seed[:12]
                if branch_summary:
                    # Context for a continuation from an earlier point: what
                    # the rest of the previous run already did (tau's
                    # BRANCH_SUMMARY_PREAMBLE seeding).
                    from .branch_summary import BRANCH_SUMMARY_PREAMBLE

                    history.insert(0, {
                        "role": "user",
                        "content": f"{BRANCH_SUMMARY_PREAMBLE}\n{branch_summary}",
                    })
                last_asst = next(
                    (m["content"] for m in reversed(seed)
                     if m["role"] == "assistant" and m["content"].strip()
                     and m["content"] != "(no response)"),
                    None,
                )
                if last_asst:
                    body = _extract_body(last_asst)
                emit("resume", session_id=resume_from, seed_turns=len(seed) // 2,
                     branch_at=branch_at)

    # ---- Hammer pre-pass: try one-shot tactics before spending LLM tokens.
    # Skipped on resume — the previous run already showed they don't work here —
    # and when the caller already knows they failed (retries).
    if body is None and not skip_hammers:
        for i, hammer in enumerate(HAMMERS, 1):
            if stop_requested():
                break
            write_file(f"  {hammer}")
            ok, output = check_file()
            emit("hammer", i=i, total=len(HAMMERS), tactic=hammer, ok=ok,
                 output="" if ok else output[-500:])
            if ok:
                return finish(True, i, target_file.read_text(), 0.0)
        emit("llm_start")
        body = "  sorry"  # placeholder so the first build reports sorry
    if body is None:
        body = "  sorry"  # hammers skipped and no resume seed: start from sorry
    write_file(body)

    for step in range(1, max_steps + 1):
        if stop_requested():
            return finish(False, step - 1, "", llm.estimate_cost(total_prompt, total_completion), stopped=True)
        ok, output = check_file()
        diags = lean.parse_diagnostics(output)
        ndiag = len(diags)
        if ok:
            emit("build", step=step, ok=True, diagnostics=0, summary="all goals solved")
            return finish(True, step, target_file.read_text(),
                          llm.estimate_cost(total_prompt, total_completion))

        report = lean.error_report(LEAN_DIR, output)
        emit("build", step=step, ok=False, diagnostics=ndiag,
             summary=(diags[0].message if diags else "sorry / not proved"),
             report=report[:4000])
        goals = get_goals(HEADER + signature + "\n" + body + "\n")
        if goals:
            emit("goals", step=step, goals=goals)

        user_msg = (
            f"Theorem signature:\n{signature}\n\n"
            f"Compiler diagnostics:\n{report}\n\n"
            + (f"Open goals at the end of your last proof attempt:\n{goals}\n\n" if goals else "")
            + "Write ONLY the tactic proof body."
        )
        history.append({"role": "user", "content": user_msg})
        emit("llm_request", step=step)
        resp = llm.chat(SYSTEM, history)
        if resp.content.startswith("[LLM error"):
            emit("llm_error", step=step, error=resp.content)
            diag.log_llm_error(
                context=diag_context, phase=f"step-{step}", error=resp.content
            )
            history.append({"role": "assistant", "content": "(no response)"})
            continue
        new_body = _extract_body(resp.content)
        if new_body:
            body = new_body
            write_file(body)
            history.append({"role": "assistant", "content": resp.content})
        total_prompt += resp.prompt_tokens
        total_completion += resp.completion_tokens
        total_tokens += resp.total_tokens
        emit("llm_response", step=step, prompt_tokens=resp.prompt_tokens,
             completion_tokens=resp.completion_tokens,
             tokens=resp.total_tokens, body=new_body)
        # Compaction beats truncation: fold old dead-end turns into a
        # summary so the model stops re-trying them (tau's memory model).
        n_msgs = len(history)
        history, summary = compact_history(history)
        # tau parity: if the estimated context crosses the auto-compaction
        # threshold (70% of the model's context window) without the turn
        # count having triggered yet, compact eagerly.
        threshold = auto_compaction_threshold_for_context_window(llm.context_window_tokens())
        if summary is None and threshold and estimate_context_tokens(SYSTEM, history) >= threshold:
            history, summary = compact_history(history, keep_turns=8, compact_at_turns=14)
        if summary:
            emit("compaction", dropped=n_msgs - len(history))

    return finish(False, max_steps, "", llm.estimate_cost(total_prompt, total_completion))
