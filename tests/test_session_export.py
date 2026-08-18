"""Tests for session export (JSONL + HTML transcript) — ported from
huggingface/tau tests/test_session_export.py, adapted to prover's flat
event-record sessions."""

from __future__ import annotations

from pathlib import Path

from agent.session_export import (
    default_session_export_path,
    export_session,
    normalize_export_format,
    render_session_html,
)


def _records() -> list[dict]:
    return [
        {"t": 1.0, "event": "start", "problem_id": "P1", "statement": "theorem t : True", "max_steps": 10},
        {"t": 1.5, "event": "build", "step": 1, "ok": False, "diagnostics": 1, "summary": "type mismatch"},
        {"t": 2.0, "event": "llm_request", "step": 2, "tokens": 100},
        {"t": 3.0, "event": "llm_response", "step": 2, "tokens": 50},
        {"t": 4.0, "event": "result", "proved": True, "steps": 3, "seconds": 4.0},
    ]


def test_default_session_export_path() -> None:
    path = default_session_export_path(Path("/tmp/session.jsonl"))
    assert path == Path("/tmp/session.html")


def test_normalize_export_format() -> None:
    assert normalize_export_format("jsonl") == "jsonl"
    assert normalize_export_format(".jsonl") == "jsonl"
    assert normalize_export_format("html") == "html"
    assert normalize_export_format(None) == "html"
    assert normalize_export_format("txt") == "html"


def test_export_session_jsonl(tmp_path: Path) -> None:
    out = export_session(_records(), tmp_path / "out.jsonl", format="jsonl")
    lines = out.read_text().strip().splitlines()
    assert len(lines) == 5
    assert '"event": "start"' in lines[0]
    assert '"proved": true' in lines[-1]


def test_export_session_html_by_suffix(tmp_path: Path) -> None:
    out = export_session(_records(), tmp_path / "out.html", title="My Run")
    text = out.read_text()
    assert "<title>My Run</title>" in text
    assert "theorem t : True" in text
    assert "PROVED" in text
    assert "type mismatch" in text


def test_export_session_format_inferred_from_jsonl_suffix(tmp_path: Path) -> None:
    out = export_session(_records(), tmp_path / "out.jsonl")
    assert '"event": "start"' in out.read_text()


def test_export_session_creates_parent_dirs(tmp_path: Path) -> None:
    out = export_session(_records(), tmp_path / "nested" / "dir" / "out.html")
    assert out.exists()


def test_render_session_html_escapes_content() -> None:
    records = [{"t": 1.0, "event": "start", "problem_id": "P", "statement": "<script>alert(1)</script>", "max_steps": 5}]
    html_text = render_session_html(records, title="<b>title</b>")
    assert "<script>" not in html_text
    assert "&lt;script&gt;" in html_text
    assert "&lt;b&gt;title&lt;/b&gt;" in html_text


def test_render_session_html_shows_source() -> None:
    html_text = render_session_html(_records(), source="/tmp/session.jsonl")
    assert "/tmp/session.jsonl" in html_text


def test_render_session_html_llm_records_summarized() -> None:
    html_text = render_session_html(_records())
    assert "llm_request step=2 tokens=100" in html_text
    assert "LLM replied (50 tokens)" in html_text


def test_render_session_html_empty() -> None:
    html_text = render_session_html([], title="Empty")
    assert "no records" in html_text


def test_export_session_unknown_format_defaults_to_html(tmp_path: Path) -> None:
    out = export_session(_records(), tmp_path / "out.txt")
    assert "<!doctype html>" in out.read_text()
