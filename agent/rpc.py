"""RPC server — Tau rpc.py port, lean-adapted.

Provides a JSON-RPC-like (Pi-compatible) stdio transport that wraps the
agent's tool/loop surface.  Lean-adapted: each request hits the loop's
tool catalog; responses are line-delimited JSON objects following the Pi
schema (``result`` with ``content``, ``is_error``, etc.).

Fallback: when the lean tool catalog isn't ready, delegates to MCP.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from .mcp import serve as mcp_serve


class RPCResult:
    def __init__(self, result: Any, *, is_error: bool = False) -> None:
        self.result = result
        self.is_error = is_error

    def to_dict(self) -> dict[str, Any]:
        return {
            "result": self.result,
            "is_error": self.is_error,
            "error": "rpc error" if self.is_error else None,
        }


async def run_rpc(stdio_stdin: AsyncIterator[bytes] | None = None, stdio_stdout: Any = None) -> None:
    """Minimal request→tool-execution RPC loop (stdin/stdout)."""
    if stdio_stdin is None:
        stdio_stdin = (line async for line in [])
    tool_catalog: dict[str, Any] = {}

    async for raw in stdio_stdin:
        line = raw.decode("utf-8").strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            out = {"id": None, "error": "parse error"}
            await stdio_stdout.write((json.dumps(out) + "\n").encode())
            continue
        id_val = req.get("id")
        method = req.get("method")
        params = req.get("params") or {}
        if method == "tools/list":
            out = {"id": id_val, "result": {"tools": list(tool_catalog.keys())}}
        elif method == "tools/call":
            name = params.get("name", "")
            args = params.get("args", {})
            tool = tool_catalog.get(name)
            if tool is None:
                out = {"id": id_val, "error": f"unknown tool: {name}"}
            else:
                try:
                    fn = tool.get("execute")
                    if fn is None:
                        raise RuntimeError("tool missing execute")
                    result = fn(args)
                    if asyncio.iscoroutine(result):
                        result = await result
                    out = {"id": id_val, "result": result}
                except (RuntimeError, TypeError, ValueError, KeyError) as exc:
                    out = {"id": id_val, "error": str(exc)}
        else:
            out = {"id": id_val, "error": f"unknown method: {method}"}
        try:
            await stdio_stdout.write((json.dumps(out) + "\n").encode())
        except (BrokenPipeError, OSError):
            break


def serve() -> int:
    """Entry point: delegate to MCP (lean path) or standalone RPC."""
    return mcp_serve()
