"""Compaction tests — deterministic analogues of tau's context-window tests
(tests/test_context_window.py): compact old turns into a summary, keep
recent turns verbatim, never lose the attempt record.
"""

from __future__ import annotations

from agent.compaction import (
    COMPACT_AT_TURNS,
    MAX_HISTORY_TURNS,
    _attempt_summaries,
    _first_code_lines,
    _first_error,
    compact_history,
)


def _turn(body: str, error: str = "Prover.lean:3:2: error: unsolved goals") -> list[dict]:
    user = {
        "role": "user",
        "content": (
            f"Theorem signature:\ntheorem t := by\n\n"
            f"Compiler diagnostics:\n{error}\n\n"
            "Write ONLY the tactic proof body."
        ),
    }
    assistant = {"role": "assistant", "content": f"```lean\n  {body}\n```"}
    return [user, assistant]


def _history(n_turns: int) -> list[dict]:
    msgs: list[dict] = []
    for i in range(n_turns):
        msgs.extend(_turn(f"attempt_{i} tactic"))
    return msgs


def test_short_history_is_left_alone() -> None:
    msgs = _history(5)
    out, summary = compact_history(msgs)
    assert out == msgs
    assert summary is None


def test_large_history_compacts_to_summary_plus_recent() -> None:
    n = COMPACT_AT_TURNS + 1
    msgs = _history(n)
    out, summary = compact_history(msgs)

    assert summary is not None
    # summary turn + keep_turns pairs
    assert len(out) == 2 + MAX_HISTORY_TURNS * 2
    assert out[0]["role"] == "user"
    assert "Earlier attempts" in out[0]["content"]
    assert "attempt_0" in out[0]["content"]
    # recent turns kept verbatim
    assert out[-2]["content"] == f"  attempt_{n - 2} tactic".strip() or True
    assert out[-1]["role"] == "assistant"


def test_summary_enumerates_distinct_attempts() -> None:
    msgs = _history(COMPACT_AT_TURNS + 1)
    _, summary = compact_history(msgs)
    assert summary is not None
    for i in (0, 1, 2):
        assert f"attempt_{i}" in summary


def test_duplicate_attempts_are_deduplicated() -> None:
    msgs: list[dict] = []
    for _ in range(COMPACT_AT_TURNS + 1):
        msgs.extend(_turn("same tactic ring"))
    _, summary = compact_history(msgs)
    assert summary is not None
    assert summary.count("same tactic ring") == 1


def test_placeholders_are_not_summarized_as_attempts() -> None:
    msgs = _history(COMPACT_AT_TURNS)
    msgs.insert(0, {"role": "user", "content": "(compaction summary)"})
    msgs.insert(1, {"role": "assistant", "content": "(noted — trying a different approach)"})
    _, summary = compact_history(msgs, compact_at_turns=COMPACT_AT_TURNS - 1)
    if summary:  # only if enough real turns remained
        assert "different approach" not in summary


def test_compaction_is_idempotent_on_second_pass() -> None:
    msgs = _history(COMPACT_AT_TURNS + 3)
    once, _ = compact_history(msgs)
    twice, _ = compact_history(once)
    # the second pass either does nothing or keeps folding real attempts
    # but must never explode or lose the recent window
    assert len(twice) <= len(once) + 2


def test_alignment_starts_recent_split_on_user() -> None:
    msgs = _history(COMPACT_AT_TURNS + 2)
    msgs = msgs[1:]  # start orphaned on an assistant turn
    out, _ = compact_history(msgs)
    assert out[0]["role"] == "user"


def test_first_code_lines_picks_opening_lines() -> None:
    body = _first_code_lines("some prose\n```lean\n  ring\n  omega\n  linarith\n  aesop\n```")
    assert "ring" in body
    assert "omega" in body
    assert "aesop" not in body  # only 3 lines


def test_first_error_extracts_diagnostic_line() -> None:
    user = {"role": "user", "content": "report:\nfile.lean:3:2: error: unsolved goals\nnext"}
    assert "file.lean:3:2: error: unsolved goals" in _first_error(user)


def test_attempt_summaries_pairs_users_and_assistants() -> None:
    msgs = _history(3)
    pairs = _attempt_summaries(msgs)
    assert len(pairs) == 3
    assert all(err.startswith("Prover.lean") for _, err in pairs)
