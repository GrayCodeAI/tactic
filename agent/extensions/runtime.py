"""Extension runtime — Tau extensions/runtime.py port (Tau 37a9e43 src/tau_coding/extensions/runtime.py), lean-adapted.

``ExtensionRuntime`` dispatches extension lifecycle: load paths, emit
session-start events to hooks, compose extension tools around builtins,
decide project trust, run input hooks (transform/handled), and render
custom messages via registered renderers (with dedupe on renderer failure).

Lean adaptation: ``compose_tools`` wraps the loop's dict-form tool list
(``{"name","description","parameters","execute"}``) rather than Tau's
``ToolDefinition`` objects; hooks are plain functions.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .api import (
    AGENT_EVENT_TYPES,
    LIFECYCLE_EVENT_TYPES,
    ExtensionContext,
    NullUiBridge,
    UiBridge,
)
from .loader import LoadedExtension, load_extensions, unload_extension_modules


@dataclass(frozen=True, slots=True)
class InputHookOutcome:
    """Result of an input-hook run: either a transformation or claiming the text."""

    text: str | None = None
    handled: bool = False
    transform: str | None = None

    @classmethod
    def passthrough(cls) -> InputHookOutcome:
        return cls()


class ExtensionRuntime:
    def __init__(self, *, ui: UiBridge | None = None, session: Any = None) -> None:
        self.ui: UiBridge = ui or NullUiBridge()
        self.session = session
        self.extensions: list[LoadedExtension] = []
        self.contexts: dict[str, ExtensionContext] = {}
        self.generation = 0

    @classmethod
    def load(
        cls,
        paths: list[Path] | None = None,
        extra_paths: list[Path] | None = None,
        *,
        ui: UiBridge | None = None,
        session: Any = None,
    ) -> ExtensionRuntime:
        rt = cls(ui=ui, session=session)
        rt.reload(paths, extra_paths)
        return rt

    def reload(self, paths: list[Path] | None = None, extra_paths: list[Path] | None = None) -> tuple[list[LoadedExtension], list[tuple[Path, str]]]:
        """Unload old modules, import fresh, and wire contexts (tau reset_for_reload)."""
        self._retire_layers()
        self.extensions, failures = load_extensions(paths, extra_paths)
        self.generation += 1
        for ext in self.extensions:
            context = ExtensionContext(
                session=self.session,
                runtime=self,
                ui=self.ui,
                generation=self.generation,
            )
            self.contexts[ext.name] = context
            from .loader import _call_setup

            _call_setup(ext, context.api)
        return self.extensions, failures

    def _retire_layers(self) -> None:
        for context in self.contexts.values():
            context.retire()
        unload_extension_modules()
        self.contexts = {}

    def reset_for_reload(self) -> None:
        """Invalidate all generations + unload modules (tau reset_for_reload)."""
        self.generation = 0
        self._retire_layers()
        self.extensions = []

    @property
    def tools(self) -> dict[str, dict]:
        """Merge tools registered by all active extensions."""
        merged: dict[str, dict] = {}
        for ext in self.extensions:
            context = self.contexts.get(ext.name)
            if context is not None:
                merged.update(context.tools)
        return merged

    def compose_tools(self, builtin_tools: list[dict]) -> list[dict]:
        """Builtins first, then extension-registered tools (tau compose_tools)."""
        merged = list(builtin_tools)
        for name, spec in self.tools.items():
            if any(t.get("name") == name for t in merged):
                continue
            merged.append({"name": name, **spec})
        return merged

    def command_specs(self) -> dict[str, dict]:
        """Slash-command specs registered by all active extensions."""
        merged: dict[str, dict] = {}
        for ext in self.extensions:
            context = self.contexts.get(ext.name)
            if context is not None:
                merged.update(context.command_specs)
        return merged

    def build_command_registry(self, builtin_names: set[str] | None = None) -> dict[str, dict]:
        """Extension commands that don't collide with builtins (tau parity).

        Frontends call this to append extension `/commands` to their slash
        registry; colliding names are dropped (builtins win, tau parity).
        """
        builtin_names = builtin_names or set()
        return {
            name: spec
            for name, spec in self.command_specs().items()
            if name not in builtin_names
        }

    def emit_event(self, event: dict) -> bool:
        """Broadcast an arbitrary event to extension hooks."""
        return self._emit_event(event)

    def _emit_event(self, event: dict) -> bool:
        handled = False
        etype = str(event.get("type", ""))
        if etype not in AGENT_EVENT_TYPES and etype not in LIFECYCLE_EVENT_TYPES:
            return False
        for ext in self.extensions:
            module = ext.module
            if module is None:
                continue
            hook = getattr(module, "on_event", None)
            if hook is None or not callable(hook):
                continue
            context = self.contexts.get(ext.name)
            try:
                result = hook(context, event)
                if result:
                    handled = True
            except Exception:  # noqa: BLE001
                self.ui.message(f"extension hook error ({ext.name})")
        return handled

    def run_input_hooks(self, text: str) -> InputHookOutcome:
        """Run all extension input hooks, honoring transform/handled signals."""
        current = text
        for ext in self.extensions:
            module = ext.module
            if module is None:
                continue
            hook = getattr(module, "on_input", None)
            if hook is None or not callable(hook):
                continue
            context = self.contexts.get(ext.name)
            try:
                outcome = hook(context, current)
            except Exception:  # noqa: BLE001
                self.ui.message(f"extension input hook error ({ext.name})")
                continue
            if outcome is None:
                continue
            if isinstance(outcome, InputHookOutcome):
                if outcome.handled:
                    return outcome
                if outcome.transform is not None:
                    current = outcome.transform
                continue
            if outcome is False:
                return InputHookOutcome(handled=True)
            if isinstance(outcome, str):
                current = outcome
        return InputHookOutcome(text=current, transform=current if current != text else None)
