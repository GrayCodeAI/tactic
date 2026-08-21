"""Per-tool permission ACL — adapted from fx's permission system.

fx gates every sensitive tool through a permission system with baseline modes
(``ask``/``auto``/``yolo``) and *exact, revocable rules under stable IDs*
(``/permissions remember allow|deny <tool> <arguments-json>``).

lean-prover already has per-*project* trust (``agent/project_trust.py``). This
module adds the orthogonal, simpler slice fx models: a per-*tool* exact rule
with a stable, revocable ID. A rule binds a tool name (and optional argument
substring/pattern) to an explicit allow/deny, so you can precisely approve one
tool without granting the whole project.

Persistence: ``~/.prover/permissions.json`` — a JSON object::

    {
      "mode": "ask",                        # ask | auto | yolo
      "rules": {
        "<stable-id>": {
          "tool": "prove_theorem",
          "pattern": "",                    # optional substring of the args JSON
          "allow": true,                    # or false for deny
          "note": "my favourite hammer"
        }
      }
    }

Stable IDs are deterministic hashes of (tool, pattern) so re-adding the same
rule yields the same ID (fx-style revocable, deduplicated rules).
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from pathlib import Path
from typing import Any

from .paths import ProverPaths

VALID_MODES = ("ask", "auto", "yolo")


def _stable_id(tool: str, pattern: str) -> str:
    raw = f"{tool}\x00{pattern}".encode()
    return hashlib.sha256(raw).hexdigest()[:16]


class PermissionStore:
    """Load/save the ACL. Thread-safe via a module-local lock."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or ProverPaths().config_dir / "permissions.json"
        self._data: dict[str, Any] = {"mode": "ask", "rules": {}}
        self._dirty = False
        self._read()

    # ---- persistence ----------------------------------------------------
    def _read(self) -> None:
        try:
            if self.path.exists():
                data = json.loads(self.path.read_text())
                if isinstance(data, dict):
                    self._data = data
        except (json.JSONDecodeError, OSError):
            self._data = {"mode": "ask", "rules": {}}
        self._data.setdefault("mode", "ask")
        self._data.setdefault("rules", {})

    def save(self) -> None:
        with _LOCK:
            self._write()

    def _write(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, indent=2, ensure_ascii=False) + "\n")
        os.replace(tmp, self.path)

    # ---- accessors ------------------------------------------------------
    @property
    def mode(self) -> str:
        return self._data.get("mode", "ask")

    @mode.setter
    def mode(self, value: str) -> None:
        if value not in VALID_MODES:
            raise ValueError(f"invalid permission mode: {value}")
        self._data["mode"] = value

    def rules(self) -> dict[str, dict[str, Any]]:
        return self._data.get("rules", {})

    def add_rule(self, tool: str, pattern: str, allow: bool, note: str = "") -> str:
        """Add (or overwrite) an exact rule, returning its stable ID."""
        tool = tool.strip()
        if not tool:
            raise ValueError("tool name required")
        rid = _stable_id(tool, pattern)
        self._data.setdefault("rules", {})[rid] = {
            "tool": tool,
            "pattern": pattern,
            "allow": bool(allow),
            "note": note,
        }
        return rid

    def remove_rule(self, rid: str) -> bool:
        rules = self._data.setdefault("rules", {})
        return rules.pop(rid, None) is not None

    def get_rule(self, rid: str) -> dict[str, Any] | None:
        return self._data.get("rules", {}).get(rid)

    def lookup(self, tool: str, args: str = "") -> str | None:
        """Resolve the decision for (tool, args): 'allow' | 'deny' | None.

        Exact (tool, pattern) match where pattern is a substring of the
        serialised args decides. Most-specific (longest pattern) wins on ties.
        """
        rules = self._data.get("rules", {})
        best: tuple[int, bool] | None = None
        for r in rules.values():
            if r.get("tool") != tool:
                continue
            pattern = r.get("pattern", "")
            if pattern and pattern not in args:
                continue
            length = len(pattern)
            if best is None or length > best[0]:
                best = (length, bool(r.get("allow")))
        if best is None:
            return None
        return "allow" if best[1] else "deny"

    def check(self, tool: str, args: str = "") -> str:
        """Full decision: rule override, else baseline mode.

        Returns 'allow' | 'deny'. yolo always allows; ask defaults to deny
        (an explicit rule can still allow); auto defaults to allow.
        """
        decision = self.lookup(tool, args)
        if decision is not None:
            return decision
        mode = self.mode
        if mode == "yolo":
            return "allow"
        if mode == "auto":
            return "allow"
        return "deny"


def acl_before_tool_call(store: PermissionStore | None = None):
    """Return an async ``before_tool_call`` hook for the agent loop (step C).

    ``loop.run_agent_loop`` accepts a ``before_tool_call(call) -> (blocked,
    reason)`` callback invoked before each tool runs. This builds one from the
    ACL: a matching **deny** rule (exact tool + argument-substring pattern)
    blocks the call with an explanatory reason; everything else is allowed, so
    the gate never breaks tooling that has no explicit deny rule.
    """
    import json

    if store is None:
        store = PermissionStore()

    async def gate(call):
        args = json.dumps(call.arguments, sort_keys=True, ensure_ascii=False)
        if store.lookup(call.name, args) == "deny":
            return True, f"permission denied for tool {call.name!r} by ACL"
        return False, None

    return gate


_LOCK = threading.Lock()
