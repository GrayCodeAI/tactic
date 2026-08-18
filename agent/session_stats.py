"""Lifetime activity and usage totals for a recorded prover session
(ported from huggingface/tau session_stats.py; prover's session is a JSONL
event stream, so we aggregate the llm_request/llm_response/result records
instead of tau's message entries).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SessionStats:
    """Cumulative activity and billed usage for one session."""

    turn_count: int = 0
    steps: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost: float = 0.0


def calculate_session_stats(records: list[dict]) -> SessionStats:
    """Aggregate totals from a session's event records.

    Turn count is the number of LLM request/response cycles; steps and token
    totals come from the terminal `result` event when present, otherwise from
    summing per-request token fields.
    """
    input_tokens = 0
    output_tokens = 0
    total_tokens = 0
    llm_turns = 0
    for rec in records:
        ev = rec.get("event")
        if ev == "llm_request":
            llm_turns += 1
        elif ev == "llm_response":
            input_tokens += int(rec.get("prompt_tokens") or 0)
            output_tokens += int(rec.get("completion_tokens") or 0)
            total_tokens += int(rec.get("tokens") or 0)
        elif ev == "result":
            steps = int(rec.get("steps") or 0)
            if rec.get("prompt_tokens") is not None:
                input_tokens = int(rec.get("prompt_tokens") or 0)
            if rec.get("completion_tokens") is not None:
                output_tokens = int(rec.get("completion_tokens") or 0)
            if rec.get("total_tokens") is not None:
                total_tokens = int(rec.get("total_tokens") or 0)
            return SessionStats(
                turn_count=llm_turns,
                steps=steps,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                estimated_cost=float(rec.get("cost_usd") or 0.0),
            )
    llm_steps = llm_turns
    return SessionStats(
        turn_count=llm_turns,
        steps=llm_steps,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        estimated_cost=0.0,
    )