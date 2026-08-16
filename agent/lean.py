"""Lean 4 toolchain interface: build + diagnostic parsing."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

DIAG_RE = re.compile(
    r"^(?P<file>[^:\s]+\.lean):(?P<line>\d+):(?P<col>\d+):\s*(?P<sev>\w+):\s*(?P<msg>.*)$"
)


@dataclass
class Diagnostic:
    file: str
    line: int
    col: int
    severity: str
    message: str


def build(lean_dir: Path, timeout: int = 120) -> tuple[bool, str]:
    """Run `lake build` in lean_dir. Returns (success, raw_output)."""
    proc = subprocess.run(
        ["lake", "build"],
        cwd=lean_dir,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    output = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode == 0, output


def parse_diagnostics(output: str) -> list[Diagnostic]:
    diags = []
    for line in output.splitlines():
        m = DIAG_RE.match(line.strip())
        if m:
            diags.append(
                Diagnostic(
                    file=m.group("file"),
                    line=int(m.group("line")),
                    col=int(m.group("col")),
                    severity=m.group("sev"),
                    message=m.group("msg").strip(),
                )
            )
    return diags


def error_report(lean_dir: Path, output: str, max_diags: int = 8, context: int = 4) -> str:
    """Human/LLM-readable error report with surrounding source context."""
    diags = [d for d in parse_diagnostics(output) if d.severity in ("error", "warning")]
    if not diags:
        return output.strip()[-4000:]  # fallback: raw tail

    lines_out = []
    for d in diags[:max_diags]:
        lines_out.append(f"{d.file}:{d.line}:{d.col}: {d.severity}: {d.message}")
        src = lean_dir / d.file
        if src.exists():
            src_lines = src.read_text().splitlines()
            lo = max(0, d.line - 1 - context)
            hi = min(len(src_lines), d.line + context)
            for i in range(lo, hi):
                marker = ">" if i == d.line - 1 else " "
                lines_out.append(f"{marker} {i + 1:4d} | {src_lines[i]}")
        lines_out.append("")
    return "\n".join(lines_out)
