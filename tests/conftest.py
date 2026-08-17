"""Pin the anyio backend for Textual's app.run_test() to asyncio."""

import pytest


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def _reset_allow_select():
    """ALLOW_SELECT is set on the class; reset around each test."""
    from agent.tui import TacticApp

    TacticApp.ALLOW_SELECT = True
    yield
    TacticApp.ALLOW_SELECT = True
