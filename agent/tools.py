from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AgentTool:
    name: str
    description: str
    parameters: dict
    execute: Callable[[dict], dict]


@dataclass
class ToolResult:
    content: str
    details: dict = field(default_factory=dict)
    is_error: bool = False
    added_tool_names: list[str] | None = None


AgentToolResult = ToolResult


def lean_check_tool(lean_dir: Path) -> AgentTool:
    def _exec(args: dict) -> dict:
        from .lean import check_file

        p = Path(args.get("file", ""))
        ok, out = check_file(p, lean_dir)
        return {"ok": ok, "output": out[:4000]}

    return AgentTool(
        name="lean_check",
        description="Run lake env lean on a file and return diagnostics (Tau tools.py port)",
        parameters={"type": "object", "properties": {"file": {"type": "string"}}, "required": ["file"]},
        execute=_exec,
    )


def lsp_goals_tool(lean_dir: Path) -> AgentTool:
    def _exec(args: dict) -> dict:
        from .lsp import LeanLSP

        file = Path(args.get("file", ""))
        lsp = LeanLSP(lean_dir, file)
        try:
            if not lsp.open_file():
                return {"goals": "no goals"}
            goals = lsp.goal_at_end(file.read_text(errors="replace") if file.exists() else "")
            return {"goals": goals or "no goals"}
        finally:
            lsp.close()

    return AgentTool(
        name="lsp_goals",
        description="Get Lean goal state via LSP (Tau tools.py port)",
        parameters={"type": "object", "properties": {"file": {"type": "string"}}, "required": ["file"]},
        execute=_exec,
    )


def retrieval_tool() -> AgentTool:
    def _exec(args: dict) -> dict:
        from .retrieval import search_lemmas

        q = args.get("query", "")
        hits = search_lemmas(q, k=5)
        return {"hits": [{"name": n, "sig": s} for n, s in hits]}

    return AgentTool(
        name="retrieval_search",
        description="Keyword search over Mathlib lemma signatures (Tau tools.py port)",
        parameters={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
        execute=_exec,
    )


def default_tools(lean_dir: Path) -> list[AgentTool]:
    return [lean_check_tool(lean_dir), lsp_goals_tool(lean_dir), retrieval_tool()]
