"""Textual TUI for tactic — browse problems, watch live proof attempts, run benchmarks.

Run with: `tactic tui`
"""

from __future__ import annotations

import functools
import json
import os
from pathlib import Path
from typing import ClassVar

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import (
    DataTable,
    Footer,
    Header,
    ListItem,
    ListView,
    RichLog,
    Static,
    TabbedContent,
    TabPane,
)

from .loop import prove

REPO = Path(__file__).resolve().parent.parent
PROBLEMS_FILE = REPO / "benchmark" / "problems.json"

STATUS_MARK = {"pending": "·", "running": "▶", "proved": "✔", "failed": "✘", "stopped": "◼"}
TIER_COLOR = {"trivial": "green", "easy": "cyan", "medium": "yellow", "hard": "red"}


def load_problems() -> list[dict]:
    if not PROBLEMS_FILE.exists():
        return []
    return json.loads(PROBLEMS_FILE.read_text())


class ProblemRow(ListItem):
    """One benchmark problem with a live status marker."""

    def __init__(self, problem: dict) -> None:
        super().__init__()
        self.problem = problem
        self.status = "pending"

    def _render_str(self) -> str:
        mark = STATUS_MARK[self.status]
        tier = self.problem.get("difficulty", "?")
        color = TIER_COLOR.get(tier, "white")
        return f"{mark} [{color}]{tier:>6}[/{color}] {self.problem['id']}"

    def render(self) -> Text:
        return Text.from_markup(self._render_str())

    def set_status(self, status: str) -> None:
        self.status = status
        self.refresh()


class LeaderboardScreen(ModalScreen[None]):
    BINDINGS: ClassVar[list[Binding]] = [
        Binding("q", "dismiss(None)", "Close"),
        Binding("escape", "dismiss(None)", "Close"),
    ]

    def compose(self) -> ComposeResult:
        table = DataTable(id="board-table")
        yield table

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("#", "name", "score", "tiers", "date")
        board_file = REPO / "leaderboard.json"
        board = json.loads(board_file.read_text()) if board_file.exists() else []
        if not board:
            table.add_row("—", "(empty)", "run `tactic leaderboard --run`", "", "")
            return
        for i, e in enumerate(board, 1):
            tiers = " ".join(
                f"{t}:{v['proved']}/{v['total']}" for t, v in sorted(e.get("tiers", {}).items())
            )
            table.add_row(str(i), e.get("name", "?"), f"{e.get('score',0)}/{e.get('total','?')}",
                          tiers, e.get("date", ""))


class TacticApp(App):
    """Interactive proof agent dashboard."""

    TITLE = "tactic — Lean 4 proof agent"
    CSS = """
    #main { height: 1fr; }
    #problems { width: 46; border-right: solid $primary; }
    #status-bar { dock: bottom; height: 1; background: $panel; padding: 0 1; }
    #board-table { width: 100%; height: 100%; }
    """
    BINDINGS: ClassVar[list[Binding]] = [
        Binding("p", "prove_selected", "Prove", priority=True),
        Binding("r", "run_remaining", "Run rest", priority=True),
        Binding("s", "stop", "Stop", priority=True),
        Binding("l", "leaderboard", "Leaderboard", priority=True),
        Binding("q", "quit_app", "Quit", priority=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.problems = load_problems()
        self._stop_flag = False
        self._run_active = False
        self.counts = {"proved": 0, "failed": 0, "stopped": 0}

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main"):
            problems_list = ListView(id="problems")
            yield problems_list
            with Vertical(), TabbedContent(initial="tab-log"):
                with TabPane("Log", id="tab-log"):
                    yield RichLog(id="log", wrap=False, markup=True)
                with TabPane("Goals", id="tab-goals"):
                    yield RichLog(id="goals", wrap=False, markup=True)
                with TabPane("Proof", id="tab-proof"):
                    yield RichLog(id="proof", wrap=False, markup=True)
        yield Static(self._status_text(), id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        if not self.problems:
            self._log("[red]benchmark/problems.json not found[/red]")
            return
        problems_list = self.query_one(ListView)
        for p in self.problems:
            problems_list.append(ProblemRow(p))
        model = os.environ.get("TACTIC_MODEL", "gpt-4o (default)")
        self._log(f"model: [cyan]{model}[/cyan] — {len(self.problems)} problems loaded")
        self._log("[dim]p prove selected · r run remaining · s stop · l leaderboard · q quit[/dim]")

    def _status_text(self) -> str:
        done = self.counts["proved"] + self.counts["failed"] + self.counts["stopped"]
        state = "RUNNING" if self._run_active else "idle"
        return (f"{state:<7} proved {self.counts['proved']} · failed {self.counts['failed']} · "
                f"stopped {self.counts['stopped']} · remaining {len(self.problems) - done}")

    def _refresh_status(self) -> None:
        self.query_one("#status-bar", Static).update(self._status_text())

    def _log(self, msg: str, *args: str) -> None:
        self.query_one("#log", RichLog).write(msg, *args)

    def _set_panel(self, widget_id: str, text: str) -> None:
        log = self.query_one(f"#{widget_id}", RichLog)
        log.clear()
        if text:
            log.write(text)

    # ---------------------------------------------------------------- proving

    def _selected_problem(self) -> dict | None:
        problems_list = self.query_one(ListView)
        idx = problems_list.index
        if idx is None:
            idx = 0  # default to first row when nothing is focused yet
        if not (0 <= idx < len(self.problems)):
            return None
        return self.problems[idx]

    def action_prove_selected(self) -> None:
        if self._run_active:
            self.notify("Already running — press s to stop first.", severity="warning")
            return
        problem = self._selected_problem()
        if problem is None:
            return
        self._start_run([problem])

    def action_run_remaining(self) -> None:
        if self._run_active:
            self.notify("Already running — press s to stop first.", severity="warning")
            return
        rows = self.query(ProblemRow)
        todo = [r.problem for r in rows if r.status not in ("proved",)]
        if not todo:
            self.notify("Nothing left to run.", severity="information")
            return
        self._start_run(todo)

    def _start_run(self, problems: list[dict]) -> None:
        self._stop_flag = False
        self._run_active = True
        self._refresh_status()
        self.run_worker(functools.partial(self._run_problems, problems), thread=True, group="prove")

    def _run_problems(self, problems: list[dict]) -> None:
        for problem in problems:
            if self._stop_flag:
                break
            self.call_from_thread(self._set_row_status, problem["id"], "running")
            self.call_from_thread(self._announce, problem)
            self.call_from_thread(self._set_panel, "goals", "")
            self.call_from_thread(self._set_panel, "proof", "")
            result = prove(
                problem["statement"],
                max_steps=20,
                verbose=False,
                problem_id=problem["id"],
                goal_feedback=True,
                on_event=lambda ev, pid=problem["id"]: self._probe_event(pid, ev),
                should_stop=lambda: self._stop_flag,
            )
            status = "proved" if result.proved else ("stopped" if result.stopped else "failed")
            self.call_from_thread(self._finish_row, problem["id"], status, result)
        self.call_from_thread(self._run_done)

    def _announce(self, problem: dict) -> None:
        self._log(f"\n[bold]── {problem['id']}[/bold]  [{TIER_COLOR.get(problem['difficulty'],'white')}]"
                  f"{problem['difficulty']}[/{TIER_COLOR.get(problem['difficulty'],'white')}]")
        self._log(f"[dim]{problem['statement'][:100]}[/dim]")

    def _probe_event(self, problem_id: str, ev: dict) -> None:
        """Forward a prove() event to the UI thread."""
        self.call_from_thread(self._render_event, problem_id, ev)

    def _render_event(self, problem_id: str, ev: dict) -> None:
        """Render a prove() event record (see agent/events.py)."""
        t = ev.get("event")
        if t == "start":
            pass  # already announced
        elif t == "hammer":
            if ev.get("ok"):
                self._log(f"  [bold green]hammer {ev['i']}/{ev['total']}: `{ev['tactic']}` ✓ PROVED ∎[/bold green]")
            else:
                self._log(f"  [dim]hammer {ev['i']}/{ev['total']}: `{ev['tactic']}` ✗[/dim]")
        elif t == "llm_start":
            self._log("  [yellow]no hammer worked → LLM repair loop[/yellow]")
        elif t == "build":
            if not ev.get("ok"):
                self._log(f"  [step {ev['step']}] {ev['diagnostics']} diagnostics — {str(ev.get('summary',''))[:70]}")
        elif t == "goals":
            self._set_panel("goals", ev["goals"])
        elif t == "llm_request":
            self._log(f"  [cyan]step {ev['step']}: asking LLM…[/cyan]")
        elif t == "llm_response":
            self._log(f"  step {ev['step']}: LLM replied ({ev.get('tokens','?')} tokens)")
            self._set_panel("proof", ev.get("body", "") or "(empty)")
        elif t == "llm_error":
            self._log(f"  [red]step {ev['step']}: {str(ev.get('error',''))[:100]}[/red]")
        elif t == "result":
            if ev.get("stopped"):
                self._log(f"  [yellow]stopped by user ({ev.get('seconds',0):.1f}s)[/yellow]")
            elif ev.get("proved"):
                self._log(f"  [bold green]PROVED ∎ ({ev.get('steps')} steps, {ev.get('seconds',0):.1f}s)[/bold green]")
            else:
                self._log(f"  [bold red]FAILED after {ev.get('steps')} steps ({ev.get('seconds',0):.1f}s)[/bold red]")
            sid = ev.get("session_id")
            if sid:
                self._log(f"  [dim]session: ~/.tactic/sessions/{sid}.jsonl[/dim]")

    # ---------------------------------------------------------------- rows/status

    def _row_by_id(self, problem_id: str) -> ProblemRow | None:
        for row in self.query(ProblemRow):
            if row.problem["id"] == problem_id:
                return row
        return None

    def _set_row_status(self, problem_id: str, status: str) -> None:
        row = self._row_by_id(problem_id)
        if row:
            row.set_status(status)

    def _finish_row(self, problem_id: str, status: str, result) -> None:
        self._set_row_status(problem_id, status)
        self.counts[status] = self.counts.get(status, 0) + 1
        proof = result.proof if result.proved else ""
        if proof:
            self._set_panel("proof", proof)
        self._refresh_status()

    def _run_done(self) -> None:
        self._run_active = False
        self._refresh_status()
        self._log(f"[bold]run finished[/bold] — proved {self.counts['proved']} so far")

    # ---------------------------------------------------------------- actions

    def action_stop(self) -> None:
        if not self._run_active:
            return
        self._stop_flag = True
        self.notify("Stopping after current step…", severity="warning")
        self._log("[yellow]stop requested[/yellow]")

    def action_leaderboard(self) -> None:
        self.push_screen(LeaderboardScreen())

    def action_quit_app(self) -> None:
        self.exit()


def main() -> None:
    TacticApp().run()


if __name__ == "__main__":
    main()
