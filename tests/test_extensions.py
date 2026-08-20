"""Phase 15/16 exit-criteria tests — extension example + survival under reload.

Loads ``data/examples/extensions/hello_tool.py`` through the real
``ExtensionRuntime`` path and verifies:

* ``setup`` registers the ``hello`` tool + ``/hello`` command
* the ``read``-style tool hook runs standalone
* the input hook transforms non-slash text and passes slash commands through
* the extension survives ``reset_for_reload()`` + fresh ``reload()``
* ``build_command_registry`` drops names colliding with builtins
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agent.extensions import ExtensionRuntime, load_extensions
from agent.extensions.runtime import InputHookOutcome

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "data" / "examples" / "extensions"


@pytest.fixture
def runtime(tmp_path) -> ExtensionRuntime:
    return ExtensionRuntime.load([EXAMPLES_DIR], ui=None, session=None)


def test_hello_tool_loads_and_registers(runtime) -> None:
    names = [e.name for e in runtime.extensions]
    assert "hello_tool" in names
    ext = next(e for e in runtime.extensions if e.name == "hello_tool")
    assert ext.setup_error is None
    assert "hello" in runtime.tools
    assert "hello" in runtime.command_specs()


def test_hello_tool_execute(runtime) -> None:
    spec = runtime.tools["hello"]
    result = spec["execute"]({"who": "Prover"})
    assert "Hello, Prover!" in result["content"]


def test_hello_tool_reads_via_hook() -> None:
    from data.examples.extensions.hello_tool import hello_read_tool

    out = hello_read_tool({"path": "lean/src/Prover.lean"})
    assert "[hello-tool] would read lean/src/Prover.lean" == out["content"]


def test_hello_command_registry_no_collision(runtime) -> None:
    # "/hello" doesn't collide with a builtin, so it's visible.
    assert "hello" in runtime.build_command_registry({"help", "quit"})
    # Colliding names are dropped (builtins win).
    assert "hello" not in runtime.build_command_registry({"hello", "quit"})


def test_input_hook_transforms_and_ignores_slash(runtime) -> None:
    outcome = runtime.run_input_hooks("prove the ring lemma")
    assert isinstance(outcome, InputHookOutcome)
    assert outcome.transform == "[hello-tool] prove the ring lemma"

    passthrough = runtime.run_input_hooks("/quit")
    assert passthrough.transform is None


def test_hello_tool_survives_reload() -> None:
    rt = ExtensionRuntime.load([EXAMPLES_DIR])
    assert any(e.name == "hello_tool" for e in rt.extensions)
    rt.reset_for_reload()
    assert rt.extensions == []
    # Fresh import reloads the module cleanly.
    rt.reload([EXAMPLES_DIR])
    ext = next(e for e in rt.extensions if e.name == "hello_tool")
    assert ext.setup_error is None
    assert "hello" in rt.tools


def test_load_extensions_skips_dunder(tmp_path) -> None:
    (tmp_path / "_private.py").write_text("x = 1\n")
    loaded, failures = load_extensions([tmp_path])
    assert loaded == []
    assert failures == []


def test_export_format_includes_markdown() -> None:
    from agent.session_export import FORMATS

    assert "md" in FORMATS
