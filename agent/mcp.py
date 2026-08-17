"""MCP (Model Context Protocol) server — expose `prove` to any MCP agent.

Zero-dependency implementation of the MCP stdio transport: newline-delimited
JSON-RPC 2.0 (MCP protocol version 2025-03-26). Run via `tactic mcp` and
point any MCP client (Claude, opencode, Cursor, ...) at it:

    {"command": "tactic", "args": ["mcp"]}

Tools:
- prove_theorem {statement, max_steps?, goal_feedback?} → proof result
- benchmark_score {problems?, max_steps?} → run a subset and report scores
- problems {difficulty?} → list benchmark problems
"""

from __future__ import annotations

import json
import re
import sys

from .loop import Result

SERVER_INFO = {"name": "tactic", "version": "0.1.0"}
PROTOCOL_VERSION = "2025-03-26"

TOOLS = [
    {
        "name": "prove_theorem",
        "description": (
            "Write and verify a Lean 4 proof for a theorem statement. "
            "Lean's kernel checks the result — returns verified proof text. "
            "Statement may be given with or without `:= by` / trailing sorry."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "statement": {"type": "string", "description": "Lean theorem statement"},
                "max_steps": {"type": "integer", "default": 20, "minimum": 1},
                "goal_feedback": {"type": "boolean", "default": True},
            },
            "required": ["statement"],
        },
    },
    {
        "name": "benchmark_score",
        "description": (
            "Run part of the 100-problem graded benchmark and report the "
            "score. Useful to gauge agent strength before tackling new proofs."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "problems": {"type": "string", "default": "benchmark/problems.json"},
                "max_steps": {"type": "integer", "default": 20, "minimum": 1},
                "limit": {"type": "integer", "default": 5, "minimum": 1, "maximum": 100},
            },
        },
    },
    {
        "name": "problems",
        "description": "List benchmark problems, optionally filtered by difficulty tier.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "difficulty": {
                    "type": "string",
                    "enum": ["trivial", "easy", "medium", "hard"],
                },
            },
        },
    },
]


def _result_json(r: Result, statement: str) -> dict:
    return {
        "proved": r.proved,
        "steps": r.steps,
        "seconds": round(r.seconds, 1),
        "tokens": r.total_tokens,
        "cost_usd": round(r.estimated_cost_usd, 6),
        "proof": r.proof if r.proved else "",
        "statement": statement,
    }


def _handle_tool(name: str, args: dict) -> tuple[dict, bool]:
    """Run a tool; return (payload, is_error)."""
    from pathlib import Path

    if name == "prove_theorem":
        from .loop import prove

        statement = args.get("statement", "").strip()
        if not statement:
            return {"error": "statement is required"}, True
        r = prove(
            statement,
            max_steps=int(args.get("max_steps", 20)),
            verbose=False,
            problem_id=re.sub(r"\W+", "_", statement.split()[1])[:40] if len(statement.split()) > 1 else None,
            goal_feedback=bool(args.get("goal_feedback", True)),
        )
        return _result_json(r, statement), False

    if name == "benchmark_score":
        problems_path = Path(args.get("problems", "benchmark/problems.json"))
        if not problems_path.exists():
            return {"error": f"problems file not found: {problems_path}"}, True
        problems = json.loads(problems_path.read_text())[: int(args.get("limit", 5))]
        from .loop import prove

        results = []
        for p in problems:
            r = prove(
                p["statement"],
                max_steps=int(args.get("max_steps", 20)),
                verbose=False,
                problem_id=p["id"],
            )
            results.append({"id": p["id"], "proved": r.proved, "steps": r.steps})
        solved = sum(1 for x in results if x["proved"])
        return {"score": solved, "total": len(results), "results": results}, False

    if name == "problems":
        problems_path = Path("benchmark/problems.json")
        if not problems_path.exists():
            return {"error": "benchmark/problems.json not found"}, True
        problems = json.loads(problems_path.read_text())
        tier = args.get("difficulty")
        if tier:
            problems = [p for p in problems if p["difficulty"] == tier]
        return {"problems": problems}, False

    return {"error": f"unknown tool: {name}"}, True


def _read_message(stdin) -> dict | None:
    line = stdin.readline()
    if not line:
        return None
    line = line.strip()
    if not line:
        return None
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return None


def _write_message(msg: dict) -> None:
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def serve() -> int:
    """Run the MCP stdio server until stdin closes."""
    stdin = sys.stdin
    while True:
        msg = _read_message(stdin)
        if msg is None:
            return 0
        method = msg.get("method")
        rid = msg.get("id")
        params = msg.get("params") or {}

        if method == "initialize":
            _write_message({
                "jsonrpc": "2.0",
                "id": rid,
                "result": {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": SERVER_INFO,
                },
            })
            continue

        if method in ("notifications/initialized", "notifications/cancelled"):
            continue  # notifications: no response

        if method == "tools/list":
            _write_message({"jsonrpc": "2.0", "id": rid, "result": {"tools": TOOLS}})
            continue

        if method == "tools/call":
            name = params.get("name", "")
            args = params.get("arguments") or {}
            try:
                payload, is_error = _handle_tool(name, args)
            except Exception as e:  # noqa: BLE001 — report tool crashes as MCP results
                payload, is_error = {"error": str(e)}, True
            _write_message({
                "jsonrpc": "2.0",
                "id": rid,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(payload, indent=2)}],
                    "isError": is_error,
                },
            })
            continue

        if method == "ping":
            _write_message({"jsonrpc": "2.0", "id": rid, "result": {}})
            continue

        if rid is not None:
            _write_message({
                "jsonrpc": "2.0",
                "id": rid,
                "error": {"code": -32601, "message": f"method not found: {method}"},
            })


def main() -> None:
    # MCP server must not print anything else to stdout.
    sys.exit(serve())


if __name__ == "__main__":
    main()
