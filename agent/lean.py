"""Lean 4 toolchain interface: build + diagnostic parsing."""

from __future__ import annotations

import os
import re
import signal
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


def _run_group(cmd: list[str], cwd: Path, timeout: int) -> tuple[int, str]:
    """Run cmd in a new process group; on timeout KILL the whole group.

    subprocess.run(timeout=...) only kills the direct child — grandchildren
    (lake spawns lean) keep stdout open, so its internal drain hangs forever.
    Running in its own session and using killpg() avoids that.
    """
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
        return proc.returncode, (stdout or b"").decode(errors="replace") + (stderr or b"").decode(errors="replace")
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except OSError:
            proc.kill()
        proc.wait()
        return -1, f"(process group killed: timeout after {timeout}s)"


def build(lean_dir: Path, timeout: int = 120) -> tuple[bool, str]:
    """Run `lake build` in lean_dir.

    Returns (proved, raw_output). proved means: exit code 0 AND no
    declaration uses 'sorry' (lake treats sorry as a warning, not an error,
    so exit code alone is not enough).
    """
    returncode, output = _run_group(["lake", "build"], lean_dir, timeout)
    proved = returncode == 0 and "declaration uses 'sorry'" not in output
    return proved, output


def check_file(lean_file: Path, lean_dir: Path, timeout: int = 60) -> tuple[bool, str]:
    """Run `lake env lean` on a single file for fast, isolated verification.

    Uses `lake env` to set up the correct package environment (Mathlib, etc.).
    Returns (proved, raw_output). proved means: exit code 0 AND no
    declaration uses 'sorry'.
    """
    returncode, output = _run_group(["lake", "env", "lean", str(lean_file)], lean_dir, timeout)
    proved = returncode == 0 and "declaration uses 'sorry'" not in output
    return proved, output


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
