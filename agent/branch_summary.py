"""Model-assisted summaries for abandoned proof branches.

Tau port (tau_coding/branch_summary.py) flattened to tactic's event-record
sessions: tau summarizes an agent conversation branch; tactic summarizes the
recorded turns of a proof run that ended in failure, so a `/branch` re-run
from an earlier point knows what the old run already tried.  File-operation
section of tau's adapter maps to the problem/session identity instead (the
agent never edits files).
"""

from __future__ import annotations

from collections.abc import Sequence

from . import llm
from .session_manager import history_from_records

MAX_SUMMARY_SOURCE_MESSAGE_CHARS = 4_000
MAX_SUMMARY_SOURCE_TOTAL_CHARS = 60_000

BRANCH_SUMMARY_SYSTEM_PROMPT = (
    "You are a proof-strategy summarization assistant. Your task is to read a "
    "recorded conversation between a prover and an AI proof assistant, then "
    "produce a structured summary following the exact format specified.\n\n"
    "Do NOT continue the conversation. Do NOT attempt to prove anything. "
    "ONLY output the structured summary."
)

BRANCH_SUMMARY_PREAMBLE = (
    "The previous run explored a different point of this theorem's proof "
    "attempt before the run ended.\nSummary of that exploration:\n\n"
)

BRANCH_SUMMARY_PROMPT = """Create a structured summary of this proof attempt for context
when continuing from an earlier stage.

Use this EXACT format:

## Goal
[The theorem this branch tried to prove]

## Constraints & Preferences
- [Any constraints on tactics, imports, or proof style]
- [Or "(none)" if none were mentioned]

## Progress
### Done
- [x] [Proof steps that compiled and advanced the goal]

### In Progress
- [ ] [A partial proof state mid-branch]

### Blocked
- [Failure modes observed: which tactics/goals the loop already burned]

## Key Decisions
- **[Decision]**: [Brief rationale]

## Next Steps
1. [What should happen next to continue this proof]

Keep each section concise. Preserve exact theorem statements, tactic names,
and error messages."""


def summarize_branch_with_model(
    records: Sequence[dict],
    *,
    custom_instructions: str | None = None,
) -> str | None:
    """Return a model-generated branch summary, or None when generation fails."""
    messages = history_from_records(records)
    if not messages:
        return None

    response = llm.chat(
        system=BRANCH_SUMMARY_SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": _branch_summary_prompt(
                messages, custom_instructions=custom_instructions
            )}
        ],
        retries=1,
    )
    summary = response.content.strip()
    if not summary or summary.startswith("[LLM error"):
        return None
    start = next((r for r in records if r.get("event") == "start"), {})
    return _add_branch_summary_context(
        summary,
        problem_id=str(start.get("problem_id") or "?"),
        statement=str(start.get("statement", "")).strip(),
    )


def _branch_summary_prompt(
    messages: Sequence[dict],
    *,
    custom_instructions: str | None = None,
) -> str:
    conversation = _serialize_branch_conversation(messages)
    if custom_instructions:
        instructions = f"{BRANCH_SUMMARY_PROMPT}\n\nAdditional focus: {custom_instructions}"
    else:
        instructions = BRANCH_SUMMARY_PROMPT
    return f"<conversation>\n{conversation}\n</conversation>\n\n{instructions}"


def _serialize_branch_conversation(messages: Sequence[dict]) -> str:
    parts: list[str] = []
    remaining_chars = MAX_SUMMARY_SOURCE_TOTAL_CHARS
    omitted_count = 0

    for index, message in enumerate(messages, start=1):
        rendered = _format_summary_source_message(message)
        if len(rendered) > remaining_chars:
            omitted_count = len(messages) - index + 1
            break
        parts.append(rendered)
        remaining_chars -= len(rendered)

    if omitted_count:
        parts.append(f"[... {omitted_count} message(s) omitted because the branch was too long]")

    return "\n\n".join(parts)


def _format_summary_source_message(message: dict) -> str:
    role = message.get("role", "?")
    content = _trim_summary_source_text(str(message.get("content", "")))
    if role == "user":
        return f"[User]: {content}"
    if role == "assistant":
        return f"[Assistant]: {content}"
    return f"[{role}]: {content}"


def _trim_summary_source_text(
    text: str,
    *,
    max_chars: int = MAX_SUMMARY_SOURCE_MESSAGE_CHARS,
) -> str:
    normalized = text.strip() or "(empty)"
    if len(normalized) <= max_chars:
        return normalized
    truncated_chars = len(normalized) - max_chars
    return f"{normalized[:max_chars].rstrip()}\n\n[... {truncated_chars} more characters truncated]"


def _add_branch_summary_context(
    summary: str, *, problem_id: str, statement: str
) -> str:
    """Attach bounded context about the branch's subject (tau parity:
    tau lists read/modified files; tactic lists the theorem instead)."""
    sections = [BRANCH_SUMMARY_PREAMBLE + summary]
    sections.append(f"<problem>\n{problem_id}\n</problem>")
    sections.append(f"<statement>\n{statement[:4_000]}\n</statement>")
    return "\n\n".join(sections)