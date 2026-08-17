"""session_usage collection + dashboard tests (tau port)."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent.commands import CommandResult, create_default_command_registry
from agent.session_usage import (
    SessionUsage,
    collect_session_usage,
    estimated_request_cost,
    render_usage_dashboard,
)


class _StubSession:
    @property
    def model(self) -> str:
        return "gpt-4o"

    @property
    def session_dir(self) -> Path:
        return Path("/tmp/placeholder")

    @property
    def session_ids(self) -> list[str]:
        return ["20260101-000000-sq"]

    @property
    def current_session_id(self) -> str | None:
        return self.session_ids[0]

    @property
    def problems_total(self) -> int:
        return 100

    @property
    def counts(self) -> dict[str, int]:
        return {}

    @property
    def n_workers(self) -> int:
        return 4

    @property
    def max_workers(self) -> int:
        return 16

    @property
    def is_running(self) -> bool:
        return False


@pytest.fixture
def session():
    return _StubSession


def _rec(event: str, **kw) -> dict:
    base = {"event": event, "timestamp": 0.0}
    base.update(kw)
    return base


def test_estimated_request_cost_matches_llm() -> None:
    from agent import llm

    assert estimated_request_cost(1000, 500, "gpt-4o") == llm.estimate_cost(1000, 500, "gpt-4o")


def test_collect_session_usage_aggregates_requests() -> None:
    records = [
        _rec("llm_request"),
        _rec("llm_response", prompt_tokens=100, completion_tokens=50, tokens=150),
        _rec("llm_request"),
        _rec("llm_response", prompt_tokens=200, completion_tokens=80, tokens=280),
    ]
    usage = collect_session_usage(records, "gpt-4o")
    assert len(usage.requests) == 2
    assert usage.total_prompt == 300
    assert usage.total_output == 130
    assert usage.requests[0].number == 1
    assert usage.requests[1].estimated_cost == estimated_request_cost(200, 80, "gpt-4o")


def test_collect_session_usage_counts_compactions_as_events() -> None:
    records = [_rec("compaction"), _rec("llm_request"),
               _rec("llm_response", prompt_tokens=10, completion_tokens=5, tokens=15)]
    usage = collect_session_usage(records)
    assert usage.compactions == 1
    assert len(usage.events) == 2


def test_collect_session_usage_handles_missing_tokens() -> None:
    records = [_rec("llm_response", prompt_tokens=0, completion_tokens=0, tokens=0)]
    usage = collect_session_usage(records, "gpt-4o")
    assert usage.total_tokens == 0
    assert usage.total_cost == 0.0  # gpt-4o costs $0 for 0 tokens


def test_render_usage_dashboard_with_requests() -> None:
    records = [_rec("llm_request"), _rec("llm_response", prompt_tokens=100, completion_tokens=30, tokens=130)]
    usage = collect_session_usage(records, "gpt-4o")
    out = render_usage_dashboard(usage)
    assert "R1" in out
    assert "Tokens" in out or "tokens" in out
    assert "Total prompt input" in out


def test_render_usage_dashboard_empty() -> None:
    usage = SessionUsage()
    assert "No assistant responses" in render_usage_dashboard(usage)


def test_usage_command_registered_and_dispatches(session) -> None:
    reg = create_default_command_registry()
    assert reg.get("usage") is not None
    result = reg.execute(session, "/usage")
    assert isinstance(result, CommandResult)
    assert result.handled
    assert result.usage_requested
    assert reg.execute(session, "/usage all").usage_requested