"""Session export: JSONL passthrough and a self-contained HTML transcript.

Tau port (tau_agent's session_export) flattened to prover's event stream:
prover sessions are flat JSONL event records (agent/events.py), so the
branch-tree/compaction rendering has no counterpart here.  The HTML export
renders each record through agent/events.format() — the same human-readable
lines the CLI prints — with per-event coloring.
"""

from __future__ import annotations

import html
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from . import events

FORMATS = ("jsonl", "html", "md", "markdown")

_EVENT_COLORS = {
    "start": "#a371f7",
    "hammer": "#7bc275",
    "resume": "#7bc275",
    "llm_start": "#e0af68",
    "build": "#e0af68",
    "goals": "#a371f7",
    "compaction": "#e0af68",
    "llm_request": "#7aa2f7",
    "llm_response": "#7aa2f7",
    "llm_error": "#f7768e",
    "result": "#7bc275",
}


def default_session_export_path(session_path: Path) -> Path:
    """Return the default HTML export path for a JSONL session file."""
    return session_path.with_suffix(".html")


def normalize_export_format(format: str | None) -> str:
    """Normalize a format/suffix string to a supported format name."""
    name = (format or "").strip().lstrip(".").lower()
    if name == "markdown":
        return "md"
    if name in FORMATS:
        return name
    return "html"


def export_session(
    entries: Sequence[dict],
    output_path: Path,
    *,
    format: str | None = None,
    title: str = "Prover Session Export",
    source: str | None = None,
    cost_table: bool = True,
) -> Path:
    """Write a session export in the requested or inferred format.

    The format is taken from *format* when given, else inferred from the
    output path's suffix, defaulting to HTML. Markdown exports render the
    transcript and an appended cost table when usage records are present.
    """
    export_format = normalize_export_format(format or output_path.suffix)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if export_format == "jsonl":
        output_path.write_text(_session_jsonl_text(entries), encoding="utf-8")
    elif export_format == "md":
        cost_rows = _cost_table_rows(list(entries)) if cost_table else []
        output_path.write_text(
            render_session_markdown(entries, title=title, source=source,
                                    cost_rows=cost_rows),
            encoding="utf-8",
        )
    else:
        output_path.write_text(
            render_session_html(entries, title=title, source=source), encoding="utf-8"
        )
    return output_path


def _session_jsonl_text(entries: Sequence[dict]) -> str:
    """Serialize session records to JSONL text (one JSON object per line)."""
    lines = [json.dumps(entry, ensure_ascii=False) for entry in entries]
    return "\n".join(lines) + ("\n" if lines else "")


def render_session_html(
    entries: Sequence[dict],
    *,
    title: str = "Prover Session Export",
    source: str | None = None,
) -> str:
    """Render a self-contained HTML transcript of a session's event records."""
    rows = [_render_record(rec) for rec in entries]
    body = "\n".join(rows) if rows else "<div class='empty'>no records</div>"
    header = html.escape(title)
    source_html = (
        f"<div class='source'>source: <code>{html.escape(source)}</code></div>"
        if source
        else ""
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{header}</title>
<style>
body {{ background: #1a1b26; color: #c0caf5; font: 13px/1.5 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; max-width: 1000px; margin: 2rem auto; padding: 0 1rem; }}
h1 {{ color: #e0af68; font-size: 1.2rem; }}
.source {{ color: #565f89; margin-bottom: 1.5rem; }}
.source code {{ color: #7aa2f7; }}
.line {{ white-space: pre-wrap; word-break: break-word; margin: 0.15rem 0; }}
.empty {{ color: #565f89; }}
</style>
</head>
<body>
<h1>{header}</h1>
{source_html}
{body}
</body>
</html>
"""


def _render_record(rec: dict[str, Any]) -> str:
    """Render one event record as a colored HTML line."""
    ev = rec.get("event", "?")
    color = _EVENT_COLORS.get(ev, "#c0caf5")
    line = events.format(rec)
    if line is None:
        summary = f"{ev} step={rec.get('step', '?')}"
        if ev == "llm_request":
            summary += f" tokens={rec.get('tokens', '?')}"
        if ev == "llm_response":
            summary += f" tokens={rec.get('tokens', '?')}"
        line = summary
    return f"<div class='line' style='color:{color}'>{html.escape(line)}</div>"


def render_session_markdown(
    entries: Sequence[dict],
    *,
    title: str = "Prover Session Export",
    source: str | None = None,
    cost_rows: list[tuple[str, str, str, str]] | None = None,
) -> str:
    """Render a markdown transcript of a session's event records (tau parity).

    Appends a cost table when *cost_rows* is non-empty.
    """
    out = [f"# {title}", ""]
    if source:
        out += [f"*source: `{source}`*", ""]
    for rec in entries:
        line = events.format(rec)
        if line is None:
            continue
        ev = rec.get("event", "?")
        if ev == "result":
            out.append(f"\n## Result\n\n```\n{line}\n```\n")
        elif ev == "llm_response":
            body = str(rec.get("body") or "").strip()
            if body:
                out.append(f"\n### Response\n\n```\n{body[:2000]}\n```\n")
        else:
            out.append(f"- {line}")
    if cost_rows:
        out.append("\n## Costs\n")
        out.append("| Request | Prompt | Output | Est. cost |")
        out.append("|---------|--------|--------|-----------|")
        for number, prompt, output, cost in cost_rows:
            out.append(f"| {number} | {prompt} | {output} | {cost} |")
    return "\n".join(out).rstrip() + "\n"


def _cost_table_rows(records: list[dict[str, Any]]) -> list[tuple[str, str, str, str]]:
    """(number, prompt_tokens, output_tokens, cost) rows from llm_response records."""
    rows: list[tuple[str, str, str, str]] = []
    number = 0
    for rec in records:
        if rec.get("event") != "llm_response":
            continue
        number += 1
        prompt = int(rec.get("prompt_tokens") or 0)
        output = int(rec.get("completion_tokens") or 0)
        try:
            from . import llm

            cost = llm.estimate_cost(prompt, output, rec.get("model"))
            cost_text = "N/A" if cost is None else f"${cost:.4f}"
        except Exception:  # noqa: BLE001
            cost_text = "N/A"
        rows.append((str(number), str(prompt), str(output), cost_text))
    return rows
