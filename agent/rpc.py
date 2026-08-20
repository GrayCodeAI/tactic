from __future__ import annotations


def serve() -> int:
    from .mcp import serve as mcp_serve

    return mcp_serve()
