"""Phase 16 tests — TUI state/adapter, rendering, CLI, update/updater.

Covers the Tau-parity surfaces added in Phase 16: TuiState batching,
TuiEventAdapter AgentEvent mapping, conversation renderers, markdown
session export with cost table, the coding CLI dispatch, and the
version/update-check primitives.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agent.events import (
    AgentEndEvent,
    AgentStartEvent,
    MessageEndEvent,
    MessageStartEvent,
    ToolExecutionEndEvent,
    ToolExecutionStartEvent,
    TurnStartEvent,
)
from agent.messages import UserMessage
from agent.rendering import RenderOptions, render_conversation_transcript
from agent.tools import ToolResult
from agent.tui_adapter import TuiEventAdapter
from agent.tui_state import TuiState

# ---------------------------------------------------------------- TuiState


def test_tui_state_tool_lifecycle() -> None:
    state = TuiState()
    state.start_turn()
    display = state.add_tool_call("c1", "read", {"path": "f.lean"})
    assert state.format_tool_call_invocation(display).startswith("…")
    state.record_tool_update("c1", status="done", result_text="lean says ok")
    assert display.status == "done"
    assert "✓" in state.format_tool_call_invocation(display)
    assert state.result_preview(display) == "lean says ok"


def test_tui_state_unknown_call_id_ignored() -> None:
    state = TuiState()
    assert state.record_tool_update("missing", status="done") is None


def test_tui_state_batched_groups_and_line() -> None:
    state = TuiState()
    state.start_turn()
    state.add_tool_call("c1", "read", {})
    state.add_tool_call("c2", "edit", {})
    groups = state.batched_groups()
    assert len(groups) == 1 and groups[0].names == ("read", "edit")
    line = state.active_tool_line()
    assert line and "read" in line and "edit" in line


def test_tui_state_result_preview_truncation() -> None:
    state = TuiState()
    display = state.add_tool_call("c1", "read", {})
    state.record_tool_update("c1", result_text="x" * 5000)
    assert state.result_preview(display).endswith("[…]")


def test_tui_state_custom_markup_failure_dedupe() -> None:
    calls = {"n": 0}

    def boom(message_type, message):
        calls["n"] += 1
        raise RuntimeError("nope")

    state = TuiState(custom_markup_resolver=boom)
    assert state.resolve_custom_markup("chart", {}) is None
    assert state.resolve_custom_markup("chart", {}) is None
    assert calls["n"] == 2
    assert state.custom_failures_reported["chart"] is True


# ----------------------------------------------------------- TuiEventAdapter


def test_adapter_maps_tool_events_to_items() -> None:
    adapter = TuiEventAdapter()
    adapter.handle(AgentStartEvent())
    adapter.handle(TurnStartEvent())
    adapter.handle(ToolExecutionStartEvent(tool_call_id="c1", tool_name="read", args={"path": "x"}))
    adapter.handle(
        ToolExecutionEndEvent(tool_call_id="c1", tool_name="read", result=ToolResult(content="ok"), is_error=False)
    )
    items = adapter.drain()
    kinds = [i.kind for i in items]
    assert "tool_line" in kinds
    assert any(i.kind == "tool_update" and i.style == "success" for i in items)
    assert adapter.drain() == []


def test_adapter_error_message_item() -> None:
    adapter = TuiEventAdapter()
    message = UserMessage(content="boom")
    adapter.handle(MessageStartEvent(message=message))
    err = ToolExecutionEndEvent(
        tool_call_id="c1", tool_name="bash", result=ToolResult(content="fail", is_error=True), is_error=True
    )
    adapter.handle(ToolExecutionStartEvent(tool_call_id="c1", tool_name="bash", args={}))
    adapter.handle(err)
    items = adapter.drain()
    assert any(i.style == "error" for i in items)


def test_adapter_message_end_error_item() -> None:
    adapter = TuiEventAdapter()
    from agent.messages import TextContent, ToolResultMessage

    message = ToolResultMessage(
        tool_call_id="c1", tool_name="bash", content=[TextContent(text="bad")], is_error=True
    )
    adapter.handle(MessageEndEvent(message=message))
    items = adapter.drain()
    assert items and items[0].kind == "error"


def test_adapter_agent_end_reports_error_message() -> None:
    adapter = TuiEventAdapter()
    from agent.messages import AssistantMessage

    err_msg = AssistantMessage(content=[], model="m", stop_reason="error", error_message="provider died")
    adapter.handle(AgentEndEvent(messages=[err_msg]))
    items = adapter.drain()
    assert items and items[0].kind == "error" and "provider died" in items[0].text


# ---------------------------------------------------------------- rendering


def test_transcript_renderer_renders_typed_messages() -> None:
    from agent.messages import AssistantMessage, TextContent

    messages = [
        UserMessage(content="prove it"),
        AssistantMessage(content=[TextContent(text="```lean\nring\n```")], model="m"),
    ]
    md = render_conversation_transcript(messages, RenderOptions())
    assert "# Transcript" in md
    assert "## User" in md and "prove it" in md
    assert "## Assistant" in md and "ring" in md


def test_transcript_renderer_tool_result_preview() -> None:
    from agent.messages import TextContent, ToolResultMessage

    messages = [
        ToolResultMessage(tool_call_id="c1", tool_name="read", content=[TextContent(text="file data")])
    ]
    md = render_conversation_transcript(messages, RenderOptions())
    assert "**read**" in md and "file data" in md


# --------------------------------------------------------- markdown export


def test_markdown_export_with_cost_table(tmp_path: Path) -> None:
    from agent.session_export import export_session, normalize_export_format

    records = [
        {"event": "start", "problem_id": "demo"},
        {"event": "llm_response", "step": 1, "body": "ring", "prompt_tokens": 100, "completion_tokens": 10},
        {"event": "result", "proved": True, "steps": 1},
    ]
    assert normalize_export_format("markdown") == "md"
    out = tmp_path / "demo.md"
    export_session(records, out, title="Demo")
    text = out.read_text()
    assert "# Demo" in text
    assert "## Costs" in text
    assert "| 1 | 100 | 10 |" in text


def test_markdown_export_without_cost_table(tmp_path: Path) -> None:
    from agent.session_export import export_session

    records = [{"event": "result", "proved": False, "steps": 3}]
    out = tmp_path / "demo2.md"
    export_session(records, out, cost_table=False)
    assert "## Costs" not in out.read_text()


# --------------------------------------------------------------------- CLI


def test_cli_version(capsys) -> None:
    from agent.cli import main

    assert main(["version"]) == 0
    assert "lean-prover 0.1.0" in capsys.readouterr().out


def test_cli_export_missing_session(capsys, tmp_path) -> None:
    from agent.cli import main

    assert main(["export", str(tmp_path / "nope.jsonl")]) == 2
    assert "not found" in capsys.readouterr().err


def test_cli_export_round_trip(tmp_path, monkeypatch) -> None:
    from agent.cli import main

    session = tmp_path / "sess.jsonl"
    session.write_text('{"event": "result", "proved": true, "steps": 1}\n')
    monkeypatch.setenv("PROVER_NO_SESSIONS", "1")
    out = tmp_path / "out.html"
    assert main(["export", str(session), "--output", str(out), "--format", "html"]) == 0
    assert out.exists() and "PROVED" in out.read_text()


def test_cli_parser_requires_command() -> None:
    from agent.cli import build_parser

    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])


# ------------------------------------------------------------- updater/check


def test_update_check_cache_throttle(tmp_path, monkeypatch) -> None:
    from agent import update_check

    monkeypatch.setattr(update_check.ProverPaths, "config_dir", property(lambda self: tmp_path))
    assert update_check.should_check() is True
    monkeypatch.setattr(update_check, "_fetch_latest", lambda package, timeout=10.0: "99.0.0")
    info = update_check.check_for_updates(force=True)
    assert info.latest_version == "99.0.0"
    assert info.is_update_available is True
    # Cached now: should_check is False
    assert update_check.should_check() is False


def test_update_check_no_newer_version(tmp_path, monkeypatch) -> None:
    from agent import update_check

    monkeypatch.setattr(update_check.ProverPaths, "config_dir", property(lambda self: tmp_path))
    monkeypatch.setattr(update_check, "_fetch_latest", lambda package, timeout=10.0: "0.0.1")
    info = update_check.check_for_updates(force=True)
    assert info.is_update_available is False


def test_update_dry_run(tmp_path) -> None:
    from agent.updater import run_updater

    result = run_updater(dry_run=True)
    assert result.ok and result.returncode == 0
    assert "(dry run)" in result.output


# ------------------------------------------------------------------ commands


def test_command_result_tau_flags() -> None:
    from agent.commands import CommandResult

    r = CommandResult(
        handled=True,
        tree_picker_requested=True,
        fork_requested=True,
        fork_path="1.2",
        set_model_choice="gpt-4o",
        set_model_provider="openai",
        set_thinking="low",
        login_requested=True,
        login_provider="openai-codex",
    )
    assert r.fork_path == "1.2"
    assert r.set_model_choice == "gpt-4o"


class _FakeCommandSession:
    from typing import ClassVar

    model = "m"
    session_dir = Path("/tmp")
    session_ids: ClassVar[tuple] = ()
    current_session_id = None
    problems_total = 0
    counts: ClassVar[dict] = {}
    n_workers = 1
    max_workers = 1
    is_running = False
    thinking_level = "off"


def test_model_command_parses_provider() -> None:
    from agent import commands as cmds

    registry = cmds.create_default_command_registry()
    result = registry.execute(_FakeCommandSession(), "/model gpt-4o@openai")  # type: ignore[arg-type]
    assert result.set_model_choice == "gpt-4o"
    assert result.set_model_provider == "openai"


def test_login_command_rejects_unknown_provider() -> None:
    from agent import commands as cmds

    registry = cmds.create_default_command_registry()
    result = registry.execute(_FakeCommandSession(), "/login dropbox")  # type: ignore[arg-type]
    assert result.login_requested is False
    assert "Unknown provider" in (result.message or "")


# --------------------------------------------------------------- autocomplete


def test_completion_state_session_ids() -> None:
    from agent.autocomplete import build_completion_state
    from agent.commands import create_default_command_registry

    registry = create_default_command_registry()
    state = build_completion_state(registry, "/resume 2026", session_ids=["20260101-a", "20260102-b"])
    assert state.active and len(state.items) == 2
    assert state.current.text == "20260101-a"
    state.next()
    assert state.current.text == "20260102-b"


def test_completion_state_cycles() -> None:
    from agent.autocomplete import build_completion_state
    from agent.commands import create_default_command_registry

    registry = create_default_command_registry()
    state = build_completion_state(registry, "/mo")
    assert state.active
    first = state.current.text
    state.previous()
    state.next()
    assert state.current.text == first
