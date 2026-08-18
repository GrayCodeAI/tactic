"""rendering output-mode renderer tests (tau rendering package port)."""

from __future__ import annotations

import json

import pytest

from agent import events
from agent.rendering import (
    FinalTextRenderer,
    JsonEventRenderer,
    PrintOutputMode,
    TranscriptRenderer,
    create_event_renderer,
)


def _rec(event: str, **kw) -> dict:
    return events.record(event, **kw)


@pytest.mark.parametrize("mode,cls", [
    ("text", FinalTextRenderer),
    ("json", JsonEventRenderer),
    ("transcript", TranscriptRenderer),
])
def test_create_event_renderer_builds_each_mode(mode: str, cls: type) -> None:
    assert isinstance(create_event_renderer(PrintOutputMode(mode)), cls)


def test_create_event_renderer_rejects_unknown_mode() -> None:
    with pytest.raises(ValueError, match="Unknown output mode"):
        create_event_renderer("bogus")


def test_json_renderer_emits_one_object_per_record(capsys) -> None:
    r = JsonEventRenderer()
    recs = [_rec("start", problem_id="p", statement="t", max_steps=5),
            _rec("result", proved=True, steps=1, seconds=1.0)]
    for rec in recs:
        r.render(rec)
    ok = r.finish()
    lines = [ln for ln in capsys.readouterr().out.splitlines() if ln]
    assert len(lines) == 2
    assert json.loads(lines[0])["event"] == "start"
    assert json.loads(lines[1])["event"] == "result"
    assert ok is True


def test_json_renderer_marks_failed_finish() -> None:
    r = JsonEventRenderer()
    r.render(_rec("result", proved=False, steps=5, seconds=1.0))
    assert r.finish() is False


def test_text_renderer_prints_final_body_on_success(capsys) -> None:
    r = FinalTextRenderer()
    r.render(_rec("llm_response", step=1, body="  ring"))
    r.render(_rec("result", proved=True, steps=1, seconds=1.0))
    assert r.finish() is True
    assert "ring" in capsys.readouterr().out


def test_text_renderer_prints_errors_on_failure(capsys) -> None:
    r = FinalTextRenderer()
    r.render(_rec("llm_error", step=1, error="boom"))
    r.render(_rec("result", proved=False, steps=1, seconds=1.0))
    assert r.finish() is False
    assert "Error: boom" in capsys.readouterr().err


def test_text_renderer_reports_stopped_run(capsys) -> None:
    r = FinalTextRenderer()
    r.render(_rec("result", proved=False, steps=1, seconds=1.0, stopped=True))
    assert r.finish() is False
    assert "stopped by user" in capsys.readouterr().err


def test_transcript_renderer_prints_and_styles(capsys) -> None:
    r = TranscriptRenderer()
    r.render(_rec("hammer", i=1, total=10, tactic="ring", ok=True))
    r.render(_rec("result", proved=True, steps=1, seconds=1.0))
    out = capsys.readouterr().out
    assert "ring" in out
    assert "PROVED" in out
    assert "\x1b[" in out  # ANSI styling applied
    assert r.finish() is True


def test_transcript_renderer_marks_failed_finish() -> None:
    r = TranscriptRenderer()
    r.render(_rec("result", proved=False, steps=1, seconds=1.0))
    assert r.finish() is False
