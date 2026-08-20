"""Problem-selection tests — p/space must index the same pool the ListView shows.

The list renders the *filtered* pool, so prove-selection must resolve indices
against it; otherwise an active search proves the wrong problem.
"""

from __future__ import annotations

import pytest
from textual.widgets import ListView

from agent.tui import ProverApp

PROBLEMS = [
    {"id": f"thm{i}", "statement": f"theorem thm{i} : True := by trivial",
     "difficulty": "easy"}
    for i in range(1, 6)
]


async def _load(app: ProverApp) -> None:
    app.problems = PROBLEMS
    await app._filter_problems("")
    await app._render_problem_list(app.problems)


@pytest.mark.anyio
async def test_prove_selected_uses_filtered_pool_when_searching() -> None:
    app = ProverApp()
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        await _load(app)
        # only thm3 matches → filtered pool has one row at index 0
        await app._filter_problems("thm3")
        app.query_one("#problems-list", ListView).index = 0
        assert app._selected_problem()["id"] == "thm3"


@pytest.mark.anyio
async def test_prove_selected_uses_full_pool_without_search() -> None:
    app = ProverApp()
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        await _load(app)  # search cleared → pool is the full problem list
        assert app._search_text == ""
        assert app._filtered_problems == []
        app.query_one("#problems-list", ListView).index = 2
        assert app._selected_problem()["id"] == "thm3"


@pytest.mark.anyio
async def test_selected_index_beyond_pool_defaults_to_first_row() -> None:
    app = ProverApp()
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        app.problems = PROBLEMS
        app._search_text = "thm"
        app._filtered_problems = [PROBLEMS[0]]
        await app._render_problem_list(app._filtered_problems)
        # a stale/unfocusable index must never reach past the rendered pool
        app.query_one("#problems-list", ListView).index = 4
        assert app._selected_problem()["id"] == "thm1"


@pytest.mark.anyio
async def test_selected_index_matches_empty_search_state() -> None:
    app = ProverApp()
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        await _load(app)
        assert app._search_text == ""
        assert app._filtered_problems == []
        # hint row lives outside the list, so the fifth row is index 4
        app.query_one("#problems-list", ListView).index = 4
        assert app._selected_problem()["id"] == "thm5"


@pytest.mark.anyio
async def test_hint_rows_do_not_accumulate_across_refilters() -> None:
    app = ProverApp()
    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        await _load(app)
        await app._filter_problems("thm3")
        await app._filter_problems("")
        await app._filter_problems("thm1")
        await app._filter_problems("thm2")
        list_view = app.query_one("#problems-list", ListView)
        assert len(list_view.children) == 1  # exactly one ProblemRow remains
        assert type(list_view.children[0]).__name__ == "ProblemRow"