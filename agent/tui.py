"""Textual TUI for tactic — browse problems, watch live proof attempts,
prove custom theorems, run benchmarks in parallel, replay past sessions.

Run with: `tactic tui [-p/--parallel N]`
"""

from __future__ import annotations

import functools
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from rich.markup import escape
from rich.text import Text
from textual import events, on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.selection import Selection
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    ListItem,
    ListView,
    OptionList,
    RichLog,
    Static,
    TabbedContent,
    TabPane,
    TextArea,
)
from textual.widgets.option_list import Option

from . import session as sess
from .autocomplete import command_completions
from .commands import CommandResult, create_default_command_registry
from .loop import prove
from .terminal_title import TerminalTitleController
from .themes import (
    TuiTheme,
    available_tui_theme_names,
    get_tui_theme,
    textual_theme_variables,
    theme_css_variables,
)

REPO = Path(__file__).resolve().parent.parent
PROBLEMS_FILE = REPO / "benchmark" / "problems.json"

STATUS_MARK = {"pending": "·", "running": "▶", "proved": "✔", "failed": "✘", "stopped": "◼"}
TIER_COLOR = {"trivial": "green", "easy": "cyan", "medium": "yellow",
              "hard": "red", "custom": "magenta"}

MAX_WORKERS = 16


@dataclass(frozen=True)
class TuiSettings:
    """TUI preferences (subset of tau's TuiSettings)."""

    auto_copy_selection: bool = False
    theme: str = "tactic-dark"


def load_problems() -> list[dict]:
    if not PROBLEMS_FILE.exists():
        return []
    return json.loads(PROBLEMS_FILE.read_text())


def _put(log: RichLog, text: str, style: str = "") -> None:
    """Write a plain-text line (no markup interpretation of the content)."""
    log.write(Text(text, style=style)) if style else log.write(Text(text))


class SelectableRichLog(RichLog):
    """A RichLog whose plain text can be selected (ported from tau's
    TranscriptMessageWidget.get_selection). RichLog renders content to Strips
    and exposes no get_selection, so we track the plain-text lines ourselves
    and let Textual's Selection machinery extract from them.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._plain_lines: list[str] = []

    def write(self, content, *args, **kwargs):
        if isinstance(content, Text):
            plain = content.plain
        elif isinstance(content, str) and self.markup:
            plain = Text.from_markup(content).plain
        else:
            plain = escape(str(content)) if not isinstance(content, str) else content
        self._plain_lines.extend(plain.splitlines() or [""])
        return super().write(content, *args, **kwargs)

    def clear(self):
        self._plain_lines.clear()
        return super().clear()

    def get_selection(self, selection: Selection) -> tuple[str, str] | None:
        text = "\n".join(self._plain_lines)
        selected = selection.extract(text)
        if not selected:
            return None
        return selected, "\n"


def render_event(ev: dict, pid: str, log: RichLog, goals: RichLog,
                 errors: RichLog, proof: RichLog, tag: str = "",
                 skip_failed_hammers: bool = False) -> None:
    """Render one prove() event record into the given panels.

    Shared by the live view and the session-replay screen (agent/events.py
    defines the record shapes).
    """
    t = ev.get("event")
    if t == "start":
        goals.clear()
        errors.clear()
        proof.clear()
        _put(log, f"{tag}── {pid}  {str(ev.get('statement', ''))[:90]}", "bold")
    elif t == "hammer":
        if ev.get("ok"):
            _put(log, f"{tag}  hammer {ev['i']}/{ev['total']}: `{ev['tactic']}` ✓ PROVED ∎",
                 "bold green")
        elif not skip_failed_hammers:
            _put(log, f"{tag}  hammer {ev['i']}/{ev['total']}: `{ev['tactic']}` ✗", "dim")
    elif t == "llm_start":
        _put(log, f"{tag}  no hammer worked → LLM repair loop", "yellow")
    elif t == "build":
        if ev.get("ok"):
            return
        report = str(ev.get("report") or "(no detailed report)")
        errors.clear()
        errors.write(escape(report))
        summary = str(ev.get("summary", ""))[:80]
        _put(log, f"{tag}  [step {ev['step']}] {ev['diagnostics']} diagnostics — {summary}")
    elif t == "goals":
        goals.clear()
        goals.write(escape(str(ev.get("goals", ""))))
    elif t == "llm_request":
        _put(log, f"{tag}  step {ev['step']}: asking LLM…", "cyan")
    elif t == "llm_response":
        _put(log, f"{tag}  step {ev['step']}: LLM replied ({ev.get('tokens', '?')} tokens)")
        proof.clear()
        proof.write(escape(str(ev.get("body", "")) or "(empty)"))
    elif t == "llm_error":
        _put(log, f"{tag}  step {ev['step']}: {str(ev.get('error', ''))[:120]}", "red")
    elif t == "result":
        if ev.get("stopped"):
            _put(log, f"{tag}  stopped by user ({ev.get('seconds', 0):.1f}s)", "yellow")
        elif ev.get("proved"):
            _put(log, f"{tag}  PROVED ∎ ({ev.get('steps')} steps, {ev.get('seconds', 0):.1f}s)",
                 "bold green")
            proof.write("\n\n" + escape("── final file ──\n"))
        else:
            _put(log, f"{tag}  FAILED after {ev.get('steps')} steps ({ev.get('seconds', 0):.1f}s)",
                 "bold red")
        sid = ev.get("session_id")
        if sid:
            _put(log, f"{tag}  session: ~/.tactic/sessions/{sid}.jsonl", "dim")


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


class MessageScreen(ModalScreen[None]):
    """Output modal for slash commands (tau's CommandOutputScreen analogue).

    Its content is the copy target regardless of the global auto-copy setting
    — same rule tau applies to the session modal.
    """

    auto_copy_selection: bool = True

    CSS = """
    MessageScreen { align: center middle; }
    #command-output {
        width: 76; max-width: 90; height: auto; max-height: 70%;
        background: $panel; border: round $primary; padding: 1 2;
    }
    #command-output-body { height: auto; }
    """
    BINDINGS: ClassVar[list[Binding]] = [
        Binding("q", "dismiss(None)", "Close"),
        Binding("escape", "dismiss(None)", "Close"),
    ]

    def __init__(self, title: str, body: str) -> None:
        super().__init__()
        self._title = title
        self._body = body

    def compose(self) -> ComposeResult:
        with Vertical(id="command-output"):
            yield Static(f"[bold]{self._title}[/bold]")
            yield Static(self._body, id="command-output-body")


class ProveScreen(ModalScreen[str | None]):
    """Free-form theorem input."""

    CSS = """
    ProveScreen { align: center middle; }
    #prove-box {
        width: 90; height: 80%;
        background: $panel; border: round $primary; padding: 1 2;
    }
    #prove-input { height: 1fr; margin-bottom: 1; scrollbar-size: 1 1; }
    #prove-buttons { height: auto; dock: bottom; align-horizontal: right; }
    #prove-buttons Button { margin-left: 2; }
    """
    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+enter", "submit", "Prove", priority=True),
    ]

    PLACEHOLDER = "theorem sq_nonneg (x : ℤ) : 0 ≤ x ^ 2 := by sorry"

    def compose(self) -> ComposeResult:
        with Vertical(id="prove-box"):
            yield Static("[bold]prove a custom theorem[/bold] "
                         "[dim](statement with := by, may end in sorry)[/dim]")
            yield TextArea(self.PLACEHOLDER, id="prove-input", soft_wrap=True)
            with Horizontal(id="prove-buttons"):
                yield Button("Prove", variant="primary", id="ok")
                yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ok":
            self.action_submit()
        else:
            self.dismiss(None)

    def action_submit(self) -> None:
        code = self.query_one("#prove-input", TextArea).text.strip()
        if not code:
            self.notify("Enter a theorem statement first.", severity="warning")
            return
        self.dismiss(code)

    def action_cancel(self) -> None:
        self.dismiss(None)


class WorkersScreen(ModalScreen[int | None]):
    """Prompt for the number of parallel workers."""

    CSS = """
    WorkersScreen { align: center middle; }
    #workers-box {
        width: 60; height: 7;
        background: $panel; border: round $primary; padding: 1 2;
    }
    """
    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="workers-box"):
            yield Static(f"parallel workers [dim](1–{MAX_WORKERS})[/dim]")
            yield Input(value=str(self.app.n_workers), type="integer", id="workers-input")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        try:
            n = int(event.value)
        except ValueError:
            self.notify("Enter a number.", severity="warning")
            return
        self.dismiss(min(max(n, 1), MAX_WORKERS))

    def action_cancel(self) -> None:
        self.dismiss(None)


class ReplayScreen(ModalScreen[None]):
    """Replay a recorded JSONL session.

    Like tau's session modal, this screen always allows copying selections —
    the session text is the copy target regardless of the global setting.
    """

    auto_copy_selection: bool = True

    CSS = """
    ReplayScreen { width: 100%; height: 100%; }
    #replay-title { height: 1; background: $panel; padding: 0 1; }
    #replay-side { width: 1fr; }
    """
    BINDINGS: ClassVar[list[Binding]] = [
        Binding("q", "dismiss(None)", "Close"),
        Binding("escape", "dismiss(None)", "Close"),
        Binding("j", "raw", "Raw JSON"),
    ]

    def __init__(self, path: Path) -> None:
        super().__init__()
        self.path = path
        self.recs: list[dict] = []

    def compose(self) -> ComposeResult:
        yield Static("", id="replay-title")
        with Horizontal(id="main"):
            yield SelectableRichLog(id="rlog", wrap=False)
            with Vertical(id="replay-side"), TabbedContent(initial="tab-rproof"):
                with TabPane("Goals", id="tab-rgoals"):
                    yield SelectableRichLog(id="rgoals", wrap=False)
                with TabPane("Errors", id="tab-rerrors"):
                    yield SelectableRichLog(id="rerrors", wrap=False)
                with TabPane("Proof", id="tab-rproof"):
                    yield SelectableRichLog(id="rproof", wrap=False)

    def on_mount(self) -> None:
        self.recs = sess.read_session(self.path)
        start = next((r for r in self.recs if r.get("event") == "start"), {})
        pid = start.get("problem_id") or self.path.stem
        self.query_one("#replay-title", Static).update(
            f"replay: {self.path.stem}  ·  {str(start.get('statement', ''))[:80]}  "
            f"[dim]({len(self.recs)} events, j=raw)[/dim]"
        )
        for rec in self.recs:
            render_event(rec, pid,
                         self.query_one("#rlog", RichLog),
                         self.query_one("#rgoals", RichLog),
                         self.query_one("#rerrors", RichLog),
                         self.query_one("#rproof", RichLog),
                         skip_failed_hammers=True)

    def action_raw(self) -> None:
        log = self.query_one("#rlog", RichLog)
        log.write(Text("── raw records ──", style="bold"))
        for rec in self.recs:
            log.write(json.dumps(rec, ensure_ascii=False, default=str))


class SessionsScreen(ModalScreen[Path | None]):
    """Browse ~/.tactic/sessions and pick one to replay."""

    CSS = """
    SessionsScreen { align: center middle; }
    #sess-list {
        width: 90; height: 80%;
        background: $panel; border: round $primary; padding: 1 2;
    }
    """
    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "dismiss(None)", "Close"),
    ]

    MAX_ROWS = 50

    def __init__(self) -> None:
        super().__init__()
        self._paths: dict[str, Path] = {}

    def compose(self) -> ComposeResult:
        yield OptionList(id="sess-list")

    def on_mount(self) -> None:
        opt_list = self.query_one(OptionList)
        sessions = sess.list_sessions()[: self.MAX_ROWS]
        if not sessions:
            opt_list.add_option(Option(f"(no sessions in {sess.sessions_dir()})", id=None))
            return
        for sp in sessions:
            recs = sess.read_session(sp)
            start = next((r for r in recs if r.get("event") == "start"), {})
            result = next((r for r in recs if r.get("event") == "result"), {})
            mark = "✓" if result.get("proved") else ("◼" if result.get("stopped") else "✘")
            pid = start.get("problem_id") or "?"
            steps = result.get("steps", "?")
            secs = result.get("seconds", "?")
            opt_list.add_option(
                Option(f"{mark} {sp.stem:<48} {pid!s:<28} steps={steps} {secs}s", id=sp.stem)
            )
            self._paths[sp.stem] = sp

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option.id:
            self.dismiss(self._paths.get(event.option.id))
        else:
            self.dismiss(None)


class TacticApp(App):
    """Interactive proof agent dashboard."""

    TITLE = "tactic — Lean 4 proof agent"
    # Mirrors tau: the session modal always allows selecting (its text is the
    # copy target); the main screen follows ALLOW_SELECT which is toggled off
    # while a proof run mutates the transcript.
    CSS = """
    #main { height: 1fr; }
    #problems { width: 46; border-right: solid $primary; }
    #prompt-box { dock: bottom; height: auto; padding: 0 1; }
    #prompt { height: 1; }
    #prompt-completions { height: auto; max-height: 9; display: none; background: $panel; }
    #status-bar { dock: bottom; height: 1; background: $panel; padding: 0 1; }
    #board-table { width: 100%; height: 100%; }
    #side { width: 1fr; }
    """
    # Non-priority single-letter bindings so they don't hijack typing in the
    # prompt bar: they still fire when the problem list is focused because
    # ListView does not consume plain letters, but an Input widget does.
    BINDINGS: ClassVar[list[Binding]] = [
        Binding("p", "prove_selected", "Prove"),
        Binding("c", "custom_prove", "Custom"),
        Binding("r", "run_remaining", "Run rest"),
        Binding("w", "set_workers", "Workers"),
        Binding("s", "stop", "Stop"),
        Binding("v", "sessions", "Sessions"),
        Binding("l", "leaderboard", "Leaderboard"),
        Binding("ctrl+space", "complete_prompt", show=False),
        Binding("q", "quit_app", "Quit"),
    ]

    def __init__(self, parallel: int = 1, tui_settings: TuiSettings | None = None) -> None:
        super().__init__()
        self.problems = load_problems()
        self.n_workers = min(max(parallel, 1), MAX_WORKERS)
        self.tui_settings = tui_settings or TuiSettings()
        self._supports_pyperclip: bool | None = None
        self._terminal_title = TerminalTitleController()
        self._stop_flag = False
        self._run_active = False
        self._custom_seq = 0
        self.counts = {"proved": 0, "failed": 0, "stopped": 0}
        self.command_registry = create_default_command_registry()

    def get_theme_variables(self) -> dict[str, str]:
        """CSS variables from the active theme (tau's get_theme_variable_defaults)."""
        return theme_css_variables(self._active_theme())

    @property
    def resolved_theme(self) -> TuiTheme:
        """Active theme with tau-dark fallback (tau's TuiSettings.resolved_theme)."""
        try:
            return get_tui_theme(self.tui_settings.theme)
        except KeyError:
            return get_tui_theme("tactic-dark")

    def _active_theme(self) -> TuiTheme:
        return self.resolved_theme

    def _register_tactic_themes(self) -> None:
        """Register every available theme with Textual's theme system."""
        from textual.theme import Theme

        for name in available_tui_theme_names():
            palette = get_tui_theme(name)
            css_vars = textual_theme_variables(palette)
            self.register_theme(Theme(
                name=name,
                primary=palette.accent,
                secondary=palette.border,
                accent=palette.accent,
                warning=palette.warn,
                error=palette.error,
                success=palette.success,
                foreground=palette.screen_text,
                background=palette.screen_background,
                surface=palette.chrome_background,
                panel=palette.sidebar_background,
                dark=palette.dark,
                variables=css_vars,
            ))
        dark = self.tui_settings.theme == "tactic-dark" or self.resolved_theme.dark
        self.dark = dark

    # ------------------------------------------------------ CommandSession protocol

    @property
    def model(self) -> str:
        return os.environ.get("TACTIC_MODEL", "gpt-4o (default)")

    @property
    def session_dir(self) -> Path:
        return sess.sessions_dir()

    @property
    def session_ids(self) -> list[str]:
        return [sp.stem for sp in sess.list_sessions()]

    @property
    def problems_total(self) -> int:
        return len(self.problems)

    @property
    def is_running(self) -> bool:
        return self._run_active

    @property
    def max_workers(self) -> int:
        return MAX_WORKERS

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main"):
            problems_list = ListView(id="problems")
            yield problems_list
            with Vertical(id="side"), TabbedContent(initial="tab-log"):
                with TabPane("Log", id="tab-log"):
                    yield SelectableRichLog(id="log", wrap=False, markup=True)
                with TabPane("Goals", id="tab-goals"):
                    yield SelectableRichLog(id="goals", wrap=False, markup=True)
                with TabPane("Errors", id="tab-errors"):
                    yield SelectableRichLog(id="errors", wrap=False, markup=True)
                with TabPane("Proof", id="tab-proof"):
                    yield SelectableRichLog(id="proof", wrap=False, markup=True)
        with Vertical(id="prompt-box"):
            yield Static("", id="prompt-completions")
            yield Input(placeholder="type a slash command (/help) + Enter", id="prompt")
        yield Static(self._status_text(), id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        self._register_tactic_themes()
        with suppress(Exception):
            self.theme = self.tui_settings.theme
        self._sync_terminal_title()
        if not self.problems:
            self._log("[red]benchmark/problems.json not found[/red]")
            return
        problems_list = self.query_one(ListView)
        for p in self.problems:
            problems_list.append(ProblemRow(p))
        model = os.environ.get("TACTIC_MODEL", "gpt-4o (default)")
        self._log(f"model: [cyan]{model}[/cyan] — {len(self.problems)} problems loaded")
        self._log("[dim]p prove · c custom · r run rest · w workers · s stop · "
                  "v sessions · l board · q quit[/dim]")

    def _status_text(self) -> str:
        done = self.counts["proved"] + self.counts["failed"] + self.counts["stopped"]
        remaining = max(0, len(self.problems) - done)
        state = "RUNNING" if self._run_active else "idle"
        return (f"{state:<7} workers={self.n_workers} · proved {self.counts['proved']} · "
                f"failed {self.counts['failed']} · stopped {self.counts['stopped']} · "
                f"remaining {remaining}")

    def _refresh_status(self) -> None:
        self.query_one("#status-bar", Static).update(self._status_text())

    def _log(self, msg: str) -> None:
        self.query_one("#log", RichLog).write(msg)

    # ------------------------------------------------------------- slash commands

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "prompt":
            return
        self._refresh_completions(event.input.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "prompt":
            return
        text = event.value.strip()
        event.input.clear()
        self._hide_completions()
        if not text:
            return
        if text.startswith("/"):
            result = self.command_registry.execute(self, text)
            if not result.handled and result.message:
                self.notify(result.message, severity="warning")
            if result.handled:
                self._apply_command(result)
            return
        # Plain text: treat as an inline theorem statement.
        self.notify("Treat as `/prove`? Press p/c or use /prove <statement>.",
                    severity="information")

    def _refresh_completions(self, text: str) -> None:
        widget = self.query_one("#prompt-completions", Static)
        items = command_completions(self.command_registry, text)
        if not items:
            self._hide_completions()
            return
        widget.update(
            "\n".join(f"  {cmd:<14} {desc}" for cmd, desc in items)
        )
        widget.styles.display = "block"

    def _hide_completions(self) -> None:
        widget = self.query_one("#prompt-completions", Static)
        widget.styles.display = "none"

    def action_complete_prompt(self) -> None:
        """Tab: complete the current slash-command prefix."""
        prompt = self.query_one("#prompt", Input)
        if prompt is not self.focused:
            return
        items = command_completions(self.command_registry, prompt.value)
        if items:
            prompt.value = items[0][0] + " "
            prompt.cursor_position = len(prompt.value)
            self._hide_completions()

    def _apply_command(self, result: CommandResult) -> None:
        """Apply a CommandResult's flags (tau's TUI dispatch order)."""
        if result.message:
            if "\n" in result.message:
                self._show_command_message(result.message)
            else:
                self.notify(result.message)
        if result.clear_requested:
            self.query_one("#log", RichLog).clear()
        if result.stop_requested:
            self.action_stop()
        if result.run_requested:
            self.action_run_remaining()
        if result.prove_requested:
            if result.prove_statement:
                self._prove_statement(result.prove_statement)
            else:
                self.action_custom_prove()
        if result.workers_requested is not None:
            self.n_workers = result.workers_requested
            self._refresh_status()
        if result.sessions_picker_requested:
            self.action_sessions()
        if result.branch_requested and result.replay_session_id:
            self._branch_run(result.replay_session_id, result.branch_at)
        elif result.replay_session_id:
            self._replay_by_id(result.replay_session_id)
        if result.leaderboard_requested:
            self.action_leaderboard()
        if result.theme:
            self._set_theme(result.theme)
        if result.export_requested and result.export_destination:
            self._export_log(result.export_destination)
        if result.exit_requested:
            self.exit()

    def _show_command_message(self, body: str) -> None:
        """Show command output in a modal (tau's _show_command_message)."""
        title = "command output"
        self.push_screen(MessageScreen(title, body))

    def _set_theme(self, name: str) -> None:
        """Apply a theme by name (tau's /theme wiring)."""
        try:
            get_tui_theme(name)
        except KeyError:
            self.notify(f"Unknown theme: {name}", severity="error")
            return
        self.tui_settings = TuiSettings(
            auto_copy_selection=self.tui_settings.auto_copy_selection,
            theme=name,
        )
        with suppress(Exception):
            self.theme = name
        self.dark = get_tui_theme(name).dark

    def _prove_statement(self, statement: str) -> None:
        """Prove an inline theorem from /prove <statement>."""
        m = re.search(r"\b(?:theorem|lemma|example)\s+(\w+)", statement)
        base = m.group(1) if m else "custom"
        self._custom_seq += 1
        problem = {
            "id": f"{base}-{self._custom_seq}" if self._custom_seq > 1 else base,
            "statement": statement,
            "difficulty": "custom",
        }
        self._log(f"\n[bold magenta]custom: {problem['id']}[/bold magenta]")
        self._start_run([problem])

    def _replay_by_id(self, session_id: str) -> None:
        for sp in sess.list_sessions():
            if sp.stem == session_id:
                self.push_screen(ReplayScreen(sp))
                return

    def _branch_run(self, session_id: str, branch_at: int | None) -> None:
        """Re-run a recorded session's theorem, seeded from its history
        (tau: branch_to_entry repoints the leaf; here prove(resume_from=...))."""
        from .session_manager import SessionManager

        if self._run_active:
            self.notify("Already running — press s to stop first.", severity="warning")
            return
        rec = SessionManager().get(session_id)
        if rec is None:
            self.notify(f"Session not found: {session_id}", severity="error")
            return
        records = sess.read_session(Path(rec.path))
        start = next((r for r in records if r.get("event") == "start"), {})
        statement = start.get("statement")
        if not statement:
            self.notify("Session has no recorded statement.", severity="error")
            return
        pid = start.get("problem_id") or "branch"

        def worker() -> None:
            result = prove(
                statement, max_steps=20, verbose=False,
                problem_id=pid, goal_feedback=True,
                on_event=lambda ev: self._probe_event(pid, ev),
                should_stop=lambda: self._stop_flag,
                resume_from=session_id, branch_at=branch_at,
            )
            status = ("proved" if result.proved
                      else "stopped" if result.stopped else "failed")
            self.call_from_thread(self._finish_custom_row, pid, status, result)

        self._stop_flag = False
        self._run_active = True
        self._sync_text_selection_state()
        self._refresh_status()
        self._log(f"\n[bold]── branch {session_id}"
                  f"{' @ turn ' + str(branch_at) if branch_at is not None else ''}[/bold]")
        self.run_worker(worker, thread=True, group="prove")

    def _finish_custom_row(self, problem_id: str, status: str, result) -> None:
        """Finish handler for runs not backed by a ProblemRow (branch/custom)."""
        self.counts[status] = self.counts.get(status, 0) + 1
        proof = result.proof if result.proved else ""
        if proof:
            panel = self.query_one("#proof", RichLog)
            panel.clear()
            panel.write(escape(proof))
        self._run_active = False
        self._sync_text_selection_state()
        self._refresh_status()

    def _export_log(self, destination: Path) -> None:
        from textual.selection import SELECT_ALL

        log = self.query_one("#log", SelectableRichLog)
        text = log.get_selection(SELECT_ALL)
        try:
            destination.write_text((text[0] if text else "") + "\n")
        except OSError as exc:
            self.notify(f"Export failed: {exc}", severity="error")
            return
        self.notify(f"Log exported to {destination}")

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

    def action_custom_prove(self) -> None:
        if self._run_active:
            self.notify("Already running — press s to stop first.", severity="warning")
            return

        def got(code: str | None) -> None:
            if not code:
                return
            m = re.search(r"\b(?:theorem|lemma|example)\s+(\w+)", code)
            base = m.group(1) if m else "custom"
            self._custom_seq += 1
            problem = {
                "id": f"{base}-{self._custom_seq}" if self._custom_seq > 1 else base,
                "statement": code,
                "difficulty": "custom",
            }
            self._log(f"\n[bold magenta]custom: {problem['id']}[/bold magenta]")
            self._start_run([problem])

        self.push_screen(ProveScreen(), got)

    def action_set_workers(self) -> None:
        def got(n: int | None) -> None:
            if n is None:
                return
            self.n_workers = n
            self._log(f"workers set to {n}")
            self._refresh_status()

        self.push_screen(WorkersScreen(), got)

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
        self._sync_text_selection_state()
        self._refresh_status()
        self.run_worker(functools.partial(self._run_problems, problems, self.n_workers),
                        thread=True, group="prove")

    def _run_problems(self, problems: list[dict], workers: int) -> None:
        """Run problems — sequential or with a thread pool."""
        if workers <= 1:
            for problem in problems:
                if self._stop_flag:
                    self._mark_pending_skipped(problems)
                    break
                self._prove_one(problem)
        else:
            with ThreadPoolExecutor(max_workers=workers) as ex:
                futs = {ex.submit(self._prove_one, p): p for p in problems}
                for fut in as_completed(futs):
                    if self._stop_flag:
                        for f in futs:
                            f.cancel()
                        break
        self.call_from_thread(self._run_done)

    def _mark_pending_skipped(self, problems: list[dict]) -> None:
        pass  # rows simply stay pending; the stop log line explains it

    def _prove_one(self, problem: dict) -> None:
        """Prove a single problem (called from a worker thread)."""
        if self._stop_flag:
            return
        pid = problem["id"]
        self.call_from_thread(self._set_row_status, pid, "running")
        result = prove(
            problem["statement"],
            max_steps=20,
            verbose=False,
            problem_id=pid,
            goal_feedback=True,
            on_event=lambda ev, p=pid: self._probe_event(p, ev),
            should_stop=lambda: self._stop_flag,
        )
        status = "proved" if result.proved else ("stopped" if result.stopped else "failed")
        self.call_from_thread(self._finish_row, pid, status, result)

    def _probe_event(self, problem_id: str, ev: dict) -> None:
        """Forward a prove() event to the UI thread."""
        self.call_from_thread(self._render_event, problem_id, ev)

    def _render_event(self, problem_id: str, ev: dict) -> None:
        """Render a prove() event record into the main panels."""
        tag = f"{problem_id[:16]}: " if self.n_workers > 1 else ""
        render_event(ev, problem_id,
                     self.query_one("#log", RichLog),
                     self.query_one("#goals", RichLog),
                     self.query_one("#errors", RichLog),
                     self.query_one("#proof", RichLog),
                     tag=tag)

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
        if proof and self.n_workers <= 1:
            panel = self.query_one("#proof", RichLog)
            panel.clear()
            panel.write(escape(proof))
        self._refresh_status()

    def _run_done(self) -> None:
        self._run_active = False
        self._sync_text_selection_state()
        self._refresh_status()
        self._log(f"[bold]run finished[/bold] — proved {self.counts['proved']} so far")

    # ---------------------------------------------------------------- clipboard

    def _sync_terminal_title(self) -> None:
        """Reflect run state in the terminal tab title (tau parity)."""
        title = f"{len(self.problems)} problems · proved {self.counts.get('proved', 0)}"
        self._terminal_title.update(title, running=self._run_active)

    def on_unmount(self) -> None:
        self._terminal_title.restore()

    def _sync_text_selection_state(self) -> None:
        """Disable native text selection while the transcript is mutating (tau parity)."""
        type(self).ALLOW_SELECT = not self._run_active
        if self._run_active and self.screen_stack:
            with suppress(Exception):
                self.screen.clear_selection()

    def copy_to_clipboard(self, text: str) -> None:
        """Copy text using pyperclip when available, then Textual's fallback (tau parity)."""
        if self._supports_pyperclip is None:
            try:
                import pyperclip  # type: ignore[import-untyped]
            except ImportError:
                self._supports_pyperclip = False
            else:
                if pyperclip is not None:
                    self._supports_pyperclip = True
        if self._supports_pyperclip:
            import pyperclip  # type: ignore[import-untyped]

            with suppress(Exception):
                pyperclip.copy(text)
        super().copy_to_clipboard(text)

    @on(events.TextSelected)
    async def on_text_selected(self) -> None:
        """Optionally copy selected text automatically (tau parity)."""
        active_screen = self.screen
        if not (
            self.tui_settings.auto_copy_selection
            or getattr(active_screen, "auto_copy_selection", False)
        ):
            return
        selection = active_screen.get_selected_text()
        if selection:
            self.copy_to_clipboard(selection)
            self.notify("Copied selection to clipboard.")

    # ---------------------------------------------------------------- actions

    def action_stop(self) -> None:
        if not self._run_active:
            return
        self._stop_flag = True
        self.notify("Stopping after current step…", severity="warning")
        self._log("[yellow]stop requested[/yellow]")

    def action_sessions(self) -> None:
        def opened(path: Path | None) -> None:
            if path is not None:
                self.push_screen(ReplayScreen(path))

        self.push_screen(SessionsScreen(), opened)

    def action_leaderboard(self) -> None:
        self.push_screen(LeaderboardScreen())

    def action_quit_app(self) -> None:
        self.exit()


def main(parallel: int = 1) -> None:
    TacticApp(parallel=parallel).run()


if __name__ == "__main__":
    main()
