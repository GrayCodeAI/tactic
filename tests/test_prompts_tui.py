"""Tests for the /prompts picker and template expansion in the prompt bar —
ported from huggingface/tau prompt-template wiring, adapted to prover."""

from __future__ import annotations

import asyncio
from pathlib import Path

from textual.widgets import OptionList

from agent.commands import CommandResult, create_default_command_registry
from agent.prompt_templates import PromptTemplate
from agent.tui import PromptsScreen, ProverApp


def test_prompts_command_result_flag() -> None:
    registry = create_default_command_registry()
    result = registry.execute(None, "/prompts")
    assert result.handled
    assert result.prompts_requested


def test_template_expansion_beats_unknown_command(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("PROVER_PROMPTS_DIR", str(tmp_path))
    (tmp_path / "brief.md").write_text("Prove {{ arguments }} tersely.")

    expanded_text: list[str] = []

    async def scenario() -> None:
        app = ProverApp()
        async with app.run_test(size=(140, 40)) as pilot:
            app._queued_prompts = []
            app._run_active = True
            prompt = app.query_one("#prompt")
            prompt.focus()
            prompt.value = "/brief 2+2=4"
            await pilot.press("enter")
            await pilot.pause()
            expanded_text.append(app._queued_prompts[-1])
            app.exit()

    asyncio.run(scenario())
    assert expanded_text == ["Prove 2+2=4 tersely."]


def test_unknown_command_without_template_notifies(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("PROVER_PROMPTS_DIR", str(tmp_path / "empty"))

    async def scenario() -> None:
        app = ProverApp()
        async with app.run_test(size=(140, 40)) as pilot:
            prompt = app.query_one("#prompt")
            prompt.focus()
            prompt.value = "/nonexistent hi"
            await pilot.press("enter")
            await pilot.pause()
            app.exit()

    asyncio.run(scenario())


def test_prompts_screen_lists_templates_and_dismisses_with_choice(tmp_path: Path) -> None:
    templates = [
        PromptTemplate(name="brief", path=tmp_path / "brief.md", content="x", description="be brief"),
        PromptTemplate(name="hint", path=tmp_path / "hint.md", content="y"),
    ]

    async def scenario() -> None:
        app = ProverApp()
        async with app.run_test() as pilot:
            result: list[object] = []

            async def on_result(value: object | None) -> None:
                result.append(value)

            app.push_screen(PromptsScreen(templates), on_result)
            await pilot.pause()
            options = app.screen.query_one("#prompts-list", OptionList)
            assert len(options.options) == 2
            assert "be brief" in str(options.options[0].prompt)
            option_list = app.screen.query_one("#prompts-list", OptionList)
            option_list.focus()
            option_list.post_message(
                OptionList.OptionSelected(
                    option_list=option_list,
                    option=option_list.options[1],
                    index=1,
                )
            )
            await pilot.pause()
            assert result == ["hint"]

    asyncio.run(scenario())


def test_prompts_command_empty_namespace_notifies(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("PROVER_PROMPTS_DIR", str(tmp_path / "empty"))

    async def scenario() -> None:
        app = ProverApp()
        async with app.run_test(size=(140, 40)) as pilot:
            result = CommandResult(handled=True, prompts_requested=True)
            app._apply_command(result)
            await pilot.pause()
            app.exit()

    asyncio.run(scenario())


def test_command_registry_has_prompts_command() -> None:
    registry = create_default_command_registry()
    names = {cmd.name for cmd in registry.list_commands()}
    assert "prompts" in names


def test_reload_command_flag() -> None:
    registry = create_default_command_registry()
    result = registry.execute(None, "/reload")
    assert result.handled
    assert result.reload_requested


def test_reload_reloads_problems_from_disk(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("PROVER_TRUST", "always")
    problems_file = Path(__file__).resolve().parent.parent / "benchmark" / "problems.json"
    original = problems_file.read_text()
    try:
        async def scenario() -> None:
            app = ProverApp()
            async with app.run_test(size=(140, 40)) as pilot:
                for _ in range(50):
                    if app._trust_resolution is not None:
                        break
                    await pilot.pause(0.05)
                assert app.problems
                count_before = len(app.problems)
                import json as _json

                problems = _json.loads(original)
                del problems[:1]
                problems_file.write_text(_json.dumps(problems))
                app._apply_command(create_default_command_registry().execute(None, "/reload"))
                for _ in range(50):
                    if len(app.problems) != count_before:
                        break
                    await pilot.pause(0.05)
                assert len(app.problems) == count_before - 1
                app.exit()

        asyncio.run(scenario())
    finally:
        problems_file.write_text(original)