"""Unit tests for MCP arg validation (agent/mcp.py)."""

from __future__ import annotations

from agent import mcp


def test_validate_required_and_bounds() -> None:
    assert mcp._validate_args("problems", {}) is None
    assert mcp._validate_args("problems", {"difficulty": "hard"}) is None
    assert mcp._validate_args("problems", {"difficulty": "impossible"}) is not None
    # statement is required
    assert mcp._validate_args("prove_theorem", {}) is not None
    # max_steps respects minimum=1
    assert mcp._validate_args("prove_theorem", {"statement": "x"}) is None
    assert mcp._validate_args("prove_theorem", {"statement": "x", "max_steps": 0}) is not None
    assert mcp._validate_args("prove_theorem", {"statement": "x", "max_steps": 3}) is None
    # limit respects maximum=100
    assert mcp._validate_args("benchmark_score", {"limit": 101}) is not None
    assert mcp._validate_args("benchmark_score", {"limit": 100}) is None
    # query is required for loogle
    assert mcp._validate_args("loogle_search", {}) is not None
    assert mcp._validate_args("loogle_search", {"query": "(?a -> ?b)"}) is None
    # unknown tool
    assert mcp._validate_args("nope", {}) is not None
