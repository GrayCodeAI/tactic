"""Self-updater — Tau updater.py port (Tau 37a9e43 src/tau_coding/updater.py), lean-adapted.

Installs the latest ``lean-prover`` (or a pinned version) by upgrading the
package with whichever Python tool is available (uv > pipx > pip). The
updater never restarts the process; it prints the command the user ran and
reports the exit code.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass

from .version import current_version

DEFAULT_PACKAGE_NAME = "lean-prover"


@dataclass(frozen=True, slots=True)
class UpdateResult:
    ok: bool
    command: str
    returncode: int
    output: str


def _detect_installer() -> list[str]:
    """Prefer uv > pipx > pip; return the base command to upgrade with."""
    if shutil.which("uv"):
        return ["uv", "pip", "install", "--upgrade"]
    if shutil.which("pipx"):
        return ["pipx", "upgrade"]
    return [sys.executable, "-m", "pip", "install", "--upgrade"]


def run_updater(
    package: str = DEFAULT_PACKAGE_NAME,
    *,
    version: str | None = None,
    dry_run: bool = False,
) -> UpdateResult:
    """Upgrade (or pin) the package; never raises.

    ``dry_run`` shows the command without running it.
    """
    target = package if version is None else f"{package}=={version}"
    installer = _detect_installer()

    # pipx upgrades by package name only; version pinning requires `pipx install --force`
    if installer[0] == "pipx":
        command = installer + [package] if version is None else ["pipx", "install", "--force", target]
    else:
        command = installer + [target]

    if dry_run:
        return UpdateResult(ok=True, command=" ".join(command), returncode=0, output="(dry run)")

    current = current_version()
    try:
        proc = subprocess.run(
            command, capture_output=True, text=True, timeout=300, check=False
        )
    except (subprocess.SubprocessError, OSError) as exc:
        return UpdateResult(ok=False, command=" ".join(command), returncode=-1, output=str(exc))

    after = current_version()
    changed = after != current
    tail = (proc.stdout or "").strip().splitlines()
    output = "\n".join(tail[-5:]) if tail else (proc.stderr or "").strip()
    return UpdateResult(
        ok=proc.returncode == 0,
        command=" ".join(command),
        returncode=proc.returncode,
        output=output or f"ran as {'upgrade' if changed else 'no-op'}: {current} -> {after}",
    )
