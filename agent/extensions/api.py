"""Extension API surface — Tau extensions/api.py port, lean-adapted.

Provides the contract extensions code against: ``ExtensionContext`` (the
object passed to ``setup()`` / the registry), ``ExtensionApi`` (its public
attribute surface), plus the UI bridge protocol + null/stderr fallbacks and
custom message/result renderer hooks.

Adaptations vs Tau: the Textual ``Widget`` / ``Widget``-based
``ComponentBridge`` seam is duck-typed (the binder can register a renderable
object instead of a Textual ``Widget``). ``AGENT_EVENT_TYPES`` /
``LIFECYCLE_EVENT_TYPES`` are frozen tuples used as command keys.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

AGENT_EVENT_TYPES = (
    "agent_start",
    "agent_end",
    "turn_start",
    "turn_end",
    "message_start",
    "message_update",
    "message_end",
    "tool_execution_start",
    "tool_execution_update",
    "tool_execution_end",
)
LIFECYCLE_EVENT_TYPES = (
    "session_start",
    "session_end",
    "reload",
    "model_changed",
)


@runtime_checkable
class UiBridge(Protocol):
    """A UI bridge extensions draw through (tau UiBridge)."""

    def has_ui(self) -> bool: ...

    def message(self, text: str) -> None: ...

    def toast(self, text: str) -> None: ...

    def select(self, options: list[str], prompt: str = "") -> str | None: ...

    def confirm(self, prompt: str, default: bool = False) -> bool | None: ...

    def input(self, prompt: str = "", password: bool = False) -> str | None: ...

    def get_theme(self) -> dict[str, Any]: ...

    def set_theme(self, name: str | None) -> None: ...

    def set_slot_widget(self, slot: str, widget: Any) -> None: ...

    def clear_components(self) -> None: ...

    def open_main_view(self, title: str, factory: Any) -> None: ...

    def register_key_interceptor(self, key: str, callback: Any) -> None: ...


class NullUiBridge:
    """UI bridge that answers nothing and discards all rendering."""

    def has_ui(self) -> bool:
        return False

    def message(self, text: str) -> None:
        pass

    def toast(self, text: str) -> None:
        pass

    def select(self, options: list[str], prompt: str = "") -> str | None:
        return None

    def confirm(self, prompt: str, default: bool = False) -> bool | None:
        return None

    def input(self, prompt: str = "", password: bool = False) -> str | None:
        return None

    def get_theme(self) -> dict[str, Any]:
        return {}

    def set_theme(self, name: str | None) -> None:
        pass

    def set_slot_widget(self, slot: str, widget: Any) -> None:
        pass

    def clear_components(self) -> None:
        pass

    def open_main_view(self, title: str, factory: Any) -> None:
        pass

    def register_key_interceptor(self, key: str, callback: Any) -> None:
        pass


class StderrUiBridge:
    """UI bridge that prints to stderr (headless RPC/CI mode)."""

    def __init__(self) -> None:
        import sys

        self._stderr = sys.stderr

    def has_ui(self) -> bool:
        return True

    def message(self, text: str) -> None:
        print(text, file=self._stderr)

    def toast(self, text: str) -> None:
        print(f"[toast] {text}", file=self._stderr)

    def select(self, options: list[str], prompt: str = "") -> str | None:
        self.message(f"{prompt} (no UI; cannot select: {options})")
        return None

    def confirm(self, prompt: str, default: bool = False) -> bool | None:
        self.message(f"{prompt} (no UI; default={default})")
        return None

    def input(self, prompt: str = "", password: bool = False) -> str | None:
        self.message(f"{prompt} (no UI; cannot prompt)")
        return None

    def get_theme(self) -> dict[str, Any]:
        return {}

    def set_theme(self, name: str | None) -> None:
        self.message(f"theme: {name}")

    def set_slot_widget(self, slot: str, widget: Any) -> None:
        pass

    def clear_components(self) -> None:
        pass

    def open_main_view(self, title: str, factory: Any) -> None:
        self.message(f"[main-view] {title}")

    def register_key_interceptor(self, key: str, callback: Any) -> None:
        pass


class CustomMessageView:
    """Registry-side handle to a custom message renderer (tau parity)."""

    def __init__(self, message_type: str, renderer: Any) -> None:
        self.message_type = message_type
        self.renderer = renderer

    def render(self, message: Any) -> Any:
        return self.renderer(message)


class MainViewHandle:
    """Handle to the main-view overlay opened by an extension."""

    def __init__(self, title: str, factory: Any) -> None:
        self.title = title
        self.factory = factory

    def open(self, bridge: UiBridge) -> None:
        bridge.open_main_view(self.title, self.factory)


class ExtensionContext:
    """The object passed to an extension's ``setup()`` callback (tau parity).

    Mirrors Tau's ``tau`` object: ``session``, ``runtime``, ``ui``,
    ``commands``, ``register_tool(...)``, ``register_renderer(...)``,
    ``main_view(title, factory)``, ``generation``.
    """

    def __init__(
        self,
        *,
        session: Any = None,
        runtime: Any = None,
        ui: UiBridge | None = None,
        commands: dict | None = None,
        generation: int = 1,
    ) -> None:
        self.session = session
        self.runtime = runtime
        self.ui: UiBridge = ui or NullUiBridge()
        self.commands = commands or {}
        self.generation = generation
        self._tools: dict[str, dict] = {}
        self._renderers: dict[str, CustomMessageView] = {}
        self._active = True

    @property
    def api(self) -> ExtensionApi:
        return ExtensionApi(self)

    def _check_active(self) -> None:
        if not self._active:
            raise RuntimeError(
                "extension context is stale (extension was unloaded or reloaded)"
            )

    def register_tool(self, name: str, spec: dict) -> None:
        self._check_active()
        self._tools[name] = dict(spec)

    def register_renderer(self, message_type: str, renderer: Any) -> None:
        self._check_active()
        self._renderers[message_type] = CustomMessageView(message_type, renderer)

    def main_view(self, title: str, factory: Any) -> MainViewHandle:
        self._check_active()
        return MainViewHandle(title=title, factory=factory)

    def retire(self) -> None:
        self._active = False

    @property
    def tools(self) -> dict[str, dict]:
        return dict(self._tools)

    @property
    def renderers(self) -> dict[str, CustomMessageView]:
        return dict(self._renderers)


class ExtensionApi:
    """Public attribute surface of an ExtensionContext (tau ExtensionApi)."""

    def __init__(self, context: ExtensionContext) -> None:
        self._context = context

    def __getattr__(self, name: str) -> Any:
        return getattr(self._context, name)


class ToolCallMarkup:
    """Delegate an extension to render a tool-call cell (tau parity).

    ``markup`` accepts an arbitrary renderer object; lean TUI maps it to a
    ``RichLog`` / ``Static`` overlay via its own binder.
    """

    def __init__(self, tool_name: str, renderer: Any) -> None:
        self.tool_name = tool_name
        self.renderer = renderer
