"""Lemma-bank planning: prove helper lemmas before the main theorem.

Under ``PROVER_LEMMA_PLAN=1`` the repair loop first asks the model to propose
≤3 helper lemmas that would make the main theorem easy. Each proposed lemma
is (1) compile-checked as a statement, (2) proven by a bounded sub-loop, and
only then (3) prepended to the main file. Unproven or ill-typed lemmas are
dropped, never kept as ``sorry`` — the main theorem is only ever preceded by
genuinely proven helpers.
"""

from __future__ import annotations

import re

from . import lean, llm

MAX_LEMMAS = 3

SYSTEM = """You are a Lean 4 / Mathlib proof planner.
Given a theorem signature, propose up to {MAX_LEMMAS} small HELPER LEMMAS that,
if proven, would make the main theorem almost immediate (e.g. via rw/exact).
Output ONLY the helper lemmas, each as a separate theorem ending in `:= by
sorry`, inside ONE ```lean code block. Rules:
- Do NOT restate or rename the main theorem.
- Keep each helper small and self-contained.
- Only state things that are actually true.
- If no helpers are useful, output nothing (an empty reply)."""

_NAME_RE = re.compile(r"^(theorem|lemma|example)\s+([A-Za-z0-9_'.]+)")
_PROOF_RE = re.compile(r":=\s*by\b")


def _normalize_lemma(text: str, idx: int) -> str:
    """Turn one model-suggested lemma into a standalone, renamed declaration."""
    code = llm.extract_lean_code(text).strip()
    m = _NAME_RE.match(code)
    if not m:
        return code
    code = code.replace(m.group(0), f"theorem prover_plan_{idx}", 1)
    if _PROOF_RE.search(code):
        code = code[:_PROOF_RE.search(code).start()].rstrip()
    return code.rstrip() + " := by\n  sorry"


def propose_lemmas(
    statement: str,
    model_name: str | None = None,
    lean_dir=None,
) -> list[str]:
    """Propose + statement-verify up to MAX_LEMMAS helpers. Never raises.

    Returns a list of normalized lemma declarations that type-check as
    statements against Mathlib. Proofs are left as ``sorry`` here — callers
    prove them (or drop them).
    """
    from .loop import HEADER, LEAN_DIR

    lean_dir = lean_dir or LEAN_DIR
    resp = llm.chat(SYSTEM, [{"role": "user", "content": statement}],
                    temperature=0.2, model_name=model_name)
    if resp.content.startswith("[LLM error"):
        return []
    chunks = re.split(r"(?=^(?:theorem|lemma)\b)", resp.content, flags=re.MULTILINE)
    out = []
    counter = 0
    for chunk in chunks:
        if not re.match(r"^(?:theorem|lemma)\b", chunk.strip()):
            continue
        counter += 1
        if counter > MAX_LEMMAS:
            break
        decl = _normalize_lemma(chunk, counter)
        if not decl.startswith("theorem prover_plan_"):
            continue
        tmp_dir = lean_dir / "tmp"
        tmp_dir.mkdir(exist_ok=True)
        tmp = tmp_dir / f"Prover_plan_{counter}.lean"
        tmp.write_text(HEADER + decl + "\n", encoding="utf-8")
        rc, _out = lean.compile_only(tmp, lean_dir, timeout=90)
        tmp.unlink(missing_ok=True)
        if rc == 0:
            out.append(decl)
    return out


def prove_lemmas(
    lemmas: list[str],
    problem_id: str | None,
    max_steps: int = 8,
    model_name: str | None = None,
) -> list[str]:
    """Prove each lemma with a bounded sub-loop; return proven declarations.

    Non-proven lemmas are silently dropped. Uses ``prove`` without lemma
    planning (no recursion).
    """
    from .loop import prove

    proven: list[str] = []
    for idx, decl in enumerate(lemmas, 1):
        r = prove(decl, max_steps=max_steps, verbose=False,
                  problem_id=f"{problem_id}__lemma_{idx}" if problem_id else None,
                  goal_feedback=False, record_session=False,
                  model_name=model_name, lemma_plan=False)
        if r.proved:
            proven.append(decl[: decl.index(":=")].rstrip() + " := by\n" + _indent_body(r.proof))
    return proven


def _indent_body(proof: str) -> str:
    return "\n".join(
        ("  " + ln.strip()) if ln.strip() else ln for ln in proof.splitlines()
    )
