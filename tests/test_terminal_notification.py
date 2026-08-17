"""Terminal notification tests — ported from huggingface/tau
tests/test_terminal_notification.py, adapted to tactic's module."""

from __future__ import annotations

import io

from agent.terminal_notification import (
    TerminalNotificationController,
    desktop_notification_protocol,
    desktop_notification_sequence,
    osc9_notification_sequence,
    osc99_notification_sequence,
    terminal_notification_supported,
)


def test_osc9_sequence_sanitized() -> None:
    assert osc9_notification_sequence("hi there") == "\x1b]9;hi there\x07"


def test_osc9_sequence_strips_control_chars_from_payload() -> None:
    seq = osc9_notification_sequence("\x1b]0;inject\x07")
    payload = seq[len("\x1b]9;"):-1]
    assert all(ord(ch) >= 32 and ch != "\x7f" for ch in payload)
    assert "\x1b]0;" not in seq


def test_osc99_sequence_sanitized() -> None:
    assert osc99_notification_sequence("hi") == "\x1b]99;;hi\x1b\\"


def test_protocol_selection() -> None:
    assert desktop_notification_protocol(environ={"KITTY_WINDOW_ID": "1"}) == "osc99"
    assert desktop_notification_protocol(environ={"TERM_PROGRAM": "ghostty"}) == "osc9"
    assert desktop_notification_protocol(environ={"TERM": "xterm-256color"}) is None


def test_desktop_notification_sequence_uses_protocol() -> None:
    seq = desktop_notification_sequence(
        "done", environ={"KITTY_WINDOW_ID": "1"}
    )
    assert seq == "\x1b]99;;done\x1b\\"


def test_supported_requires_tty_and_clean_env() -> None:
    assert not terminal_notification_supported(environ={"CI": "1"})
    assert not terminal_notification_supported(environ={"TERM": "dumb"})
    assert not terminal_notification_supported(
        environ={}, stream=io.StringIO()
    )


def test_controller_writes_bell() -> None:
    out: list[str] = []
    ctrl = TerminalNotificationController("bell", enabled=True, writer=out.append)
    ctrl.notify_turn_finished()
    assert out == ["\a"]


def test_controller_off() -> None:
    out: list[str] = []
    ctrl = TerminalNotificationController("off", enabled=True, writer=out.append)
    ctrl.notify_turn_finished()
    assert out == []


def test_controller_auto_writes_osc_for_supported_terms() -> None:
    out: list[str] = []
    ctrl = TerminalNotificationController(
        "auto", enabled=True, writer=out.append,
        environ={"KITTY_WINDOW_ID": "1"},
    )
    ctrl.notify_turn_finished()
    assert out and out[0].startswith("\x1b]99;;")


def test_controller_disables_after_write_error() -> None:
    def bad_write(_: str) -> None:
        raise OSError("stream closed")

    ctrl = TerminalNotificationController("bell", enabled=True, writer=bad_write)
    ctrl.notify_turn_finished()
    assert ctrl.enabled is False
