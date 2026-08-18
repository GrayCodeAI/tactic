"""Pin the anyio backend for Textual's app.run_test() to asyncio."""

import pytest


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def _reset_allow_select():
    """ALLOW_SELECT is set on the class; reset around each test."""
    from agent.tui import ProverApp

    ProverApp.ALLOW_SELECT = True
    yield
    ProverApp.ALLOW_SELECT = True
    # The TUI's _apply_thinking_level sets a process-level override in
    # agent.thinking; never let it leak between tests.
    from agent import thinking

    thinking.clear_thinking_level()
