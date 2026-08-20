"""Hello-tool example extension (Tau data/examples/extensions/hello_tool.py port).

Demonstrates the full extension surface:

* ``setup(tau)``   — registers a ``hello`` tool, a ``/hello`` slash command,
                     and a ``transform`` input hook
* ``on_event``     — logs lifecycle/agent events to the UI bridge
* ``on_input``     — prepends context to every prompt unless it starts with "/"

It is intentionally dependency-free so it loads under any host.
"""

from __future__ import annotations

from typing import Any

HELLO_MESSAGE = "Hello from the hello-tool extension!"


def hello_read_tool(args: dict[str, Any]) -> dict[str, Any]:
    """A toy read hook: echoes the path with a friendly annotation."""
    path = str(args.get("path", ""))
    return {"content": f"[hello-tool] would read {path or '(no path given)'}"}


def setup(tau: Any) -> None:
    """Extension entry point — called once after import."""
    tau.register_tool("hello", {
        "description": "Return a friendly greeting.",
        "parameters": {"type": "object", "properties": {"who": {"type": "string"}}},
        "execute": _execute_hello,
    })
    tau.register_command("hello", {
        "description": "Say hello from the extension.",
        "usage": "/hello",
        "handler": lambda args, context: HELLO_MESSAGE,
    })
    if hasattr(tau.ui, "message"):
        tau.ui.message("hello-tool extension loaded")


def _execute_hello(args: dict[str, Any]) -> dict[str, Any]:
    who = str(args.get("who", "Lean")).strip() or "Lean"
    return {"content": f"Hello, {who}! (from the hello-tool extension)"}


def on_event(context: Any, event: dict[str, Any]) -> bool:
    """Observe lifecycle events; claim nothing."""
    if event.get("type") in ("session_start", "session_end", "reload"):
        context.runtime.ui.toast(f"hello-tool saw {event.get('type')}")
    return False


def on_input(context: Any, text: str) -> Any:
    """Input hook: enrich non-slash prompts with provenance context."""
    if text.startswith("/"):
        return None  # don't touch slash commands
    from agent.extensions.runtime import InputHookOutcome

    return InputHookOutcome(transform=f"[hello-tool] {text}")
