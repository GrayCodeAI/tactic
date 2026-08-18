"""Tests for drag-and-drop file insertion in the TUI prompt — ported from
huggingface/tau tests/test_tui_file_drop.py, adapted to prover's prompt."""

from __future__ import annotations

import asyncio
from pathlib import Path

from textual import events
from textual.app import App, ComposeResult

from agent.file_drop import normalize_dropped_paths
from agent.tui import PromptInput


def _escaped(path: Path) -> str:
    """Render a path the way terminals do when a file is dropped."""
    return str(path).replace(" ", "\\ ")


class TestNormalizeDroppedPaths:
    def test_plain_absolute_path_passes_through(self, tmp_path: Path) -> None:
        file = tmp_path / "notes.txt"
        file.touch()

        assert normalize_dropped_paths(str(file)) == str(file)

    def test_escaped_spaces_are_unescaped_and_quoted(self, tmp_path: Path) -> None:
        file = tmp_path / "my file.png"
        file.touch()

        assert normalize_dropped_paths(_escaped(file)) == f'"{file}"'

    def test_bare_path_with_spaces_is_quoted(self, tmp_path: Path) -> None:
        file = tmp_path / "my file.png"
        file.touch()

        assert normalize_dropped_paths(str(file)) == f'"{file}"'

    def test_double_quoted_path_is_normalized(self, tmp_path: Path) -> None:
        file = tmp_path / "my file.png"
        file.touch()

        assert normalize_dropped_paths(f'"{file}"') == f'"{file}"'

    def test_multiple_dropped_files_join_with_spaces(self, tmp_path: Path) -> None:
        first = tmp_path / "first.txt"
        second = tmp_path / "second file.txt"
        first.touch()
        second.touch()

        dropped = f"{first} {_escaped(second)}"

        assert normalize_dropped_paths(dropped) == f'{first} "{second}"'

    def test_newline_separated_paths_join_with_spaces(self, tmp_path: Path) -> None:
        first = tmp_path / "first.txt"
        second = tmp_path / "second.txt"
        first.touch()
        second.touch()

        assert normalize_dropped_paths(f"{first}\n{second}\n") == f"{first} {second}"

    def test_directory_path_is_accepted(self, tmp_path: Path) -> None:
        directory = tmp_path / "some dir"
        directory.mkdir()

        assert normalize_dropped_paths(_escaped(directory)) == f'"{directory}"'

    def test_file_uri_is_converted_to_local_path(self, tmp_path: Path) -> None:
        file = tmp_path / "my file.png"
        file.touch()
        uri = "file://" + str(file).replace(" ", "%20")

        assert normalize_dropped_paths(uri) == f'"{file}"'

    def test_missing_path_is_not_a_drop(self, tmp_path: Path) -> None:
        assert normalize_dropped_paths(str(tmp_path / "missing.txt")) is None

    def test_relative_path_is_not_a_drop(self) -> None:
        assert normalize_dropped_paths("pyproject.toml") is None

    def test_prose_is_not_a_drop(self) -> None:
        assert normalize_dropped_paths("please summarize /tmp") is None

    def test_blank_text_is_not_a_drop(self) -> None:
        assert normalize_dropped_paths("   \n ") is None

    def test_unbalanced_quotes_are_not_a_drop(self, tmp_path: Path) -> None:
        file = tmp_path / "notes.txt"
        file.touch()

        assert normalize_dropped_paths(f'"{file}') is None


class PromptHarness(App):
    """Minimal app that mirrors ProverApp's paste interception."""

    def compose(self) -> ComposeResult:
        yield PromptInput(placeholder="", id="prompt")

    async def on_event(self, event: events.Event) -> None:
        if isinstance(event, events.Paste):
            prompt = self.query_one_optional("#prompt", PromptInput)
            if prompt is not None and (self.focused is None or self.focused is prompt):
                event.stop()
                prompt.insert_pasted_text(event.text)
                return
        await super().on_event(event)


class TestPromptPasteHandler:
    def test_non_path_paste_keeps_default_behavior(self) -> None:
        async def scenario() -> None:
            app = PromptHarness()
            async with app.run_test() as pilot:
                prompt = app.query_one("#prompt", PromptInput)
                prompt.value = "existing content"
                await pilot.pause()
                app.post_message(events.Paste("just some regular text"))
                await pilot.pause()
                assert prompt.value == "existing contentjust some regular text"

        asyncio.run(scenario())

    def test_dropped_path_inserts_normalized_text(self, tmp_path: Path) -> None:
        file = tmp_path / "my file.lean"
        file.touch()

        async def scenario() -> None:
            app = PromptHarness()
            async with app.run_test() as pilot:
                prompt = app.query_one("#prompt", PromptInput)
                await pilot.pause()
                app.post_message(events.Paste(str(file)))
                await pilot.pause()
                assert prompt.value == f'"{file}" '

        asyncio.run(scenario())

    def test_drop_preserves_existing_text(self, tmp_path: Path) -> None:
        file = tmp_path / "notes.txt"
        file.touch()

        async def scenario() -> None:
            app = PromptHarness()
            async with app.run_test() as pilot:
                prompt = app.query_one("#prompt", PromptInput)
                prompt.value = "prove "
                await pilot.pause()
                app.post_message(events.Paste(str(file)))
                await pilot.pause()
                assert prompt.value == f"prove {file} "

        asyncio.run(scenario())

    def test_drop_mid_text_separates_both_sides(self, tmp_path: Path) -> None:
        file = tmp_path / "notes.txt"
        file.touch()

        async def scenario() -> None:
            app = PromptHarness()
            async with app.run_test() as pilot:
                prompt = app.query_one("#prompt", PromptInput)
                prompt.value = "comparethese"
                prompt.cursor_position = len("compare")
                await pilot.pause()
                app.post_message(events.Paste(str(file)))
                await pilot.pause()
                assert prompt.value == f"compare {file} these"

        asyncio.run(scenario())

    def test_unfocused_paste_routes_through_app_handler(self, tmp_path: Path) -> None:
        app = PromptHarness()
        file = tmp_path / "drop.txt"
        file.touch()

        async def scenario() -> None:
            async with app.run_test() as pilot:
                prompt = app.query_one("#prompt", PromptInput)
                prompt.blur()
                await pilot.pause()
                app.post_message(events.Paste(str(file)))
                await pilot.pause()
                assert prompt.value == f"{file} "

        asyncio.run(scenario())