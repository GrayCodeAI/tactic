"""Tests for markdown prompt templates — ported from
huggingface/tau tests/test_prompt_templates.py, with tau's multi-namespace
resource paths flattened to tactic's prompts-dirs list."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent.prompt_templates import (
    PromptTemplate,
    ResourceError,
    expand_prompt_template_command,
    is_prompt_template_candidate,
    load_prompt_templates,
    load_prompt_templates_with_diagnostics,
    render_prompt_template,
)


def test_load_prompt_templates_missing_directory_returns_empty(tmp_path: Path) -> None:
    assert load_prompt_templates([tmp_path / "missing"]) == []


def test_load_prompt_templates_from_markdown_files(tmp_path: Path) -> None:
    directory = tmp_path / "prompts"
    directory.mkdir()
    (directory / "brief.md").write_text("description: concise\nProve {{ arguments }} briefly.")
    (directory / "elaborate.md").write_text("Prove step by step.")
    (directory / "notes.txt").write_text("ignored")

    templates = load_prompt_templates([directory])
    assert [t.name for t in templates] == ["brief", "elaborate"]
    brief = templates[0]
    assert brief.description == "concise"
    assert "Prove" in brief.content


def test_later_prompt_directory_overrides_earlier(tmp_path: Path) -> None:
    low = tmp_path / "low"
    high = tmp_path / "high"
    low.mkdir()
    high.mkdir()
    (low / "brief.md").write_text("low version")
    (high / "brief.md").write_text("high version")

    templates = load_prompt_templates([low, high])
    assert templates[0].content == "high version"


def test_load_prompt_templates_with_diagnostics_reports_overrides(tmp_path: Path) -> None:
    low = tmp_path / "low"
    high = tmp_path / "high"
    low.mkdir()
    high.mkdir()
    (low / "brief.md").write_text("low version")
    (high / "brief.md").write_text("high version")

    templates, diagnostics = load_prompt_templates_with_diagnostics([low, high])
    assert len(templates) == 1
    assert any("overrides" in diagnostic.message for diagnostic in diagnostics)


def test_reserved_template_names_are_ignored(tmp_path: Path) -> None:
    directory = tmp_path / "prompts"
    directory.mkdir()
    for reserved in ("prompts", "skills", "tools", "reload"):
        (directory / f"{reserved}.md").write_text("reserved")
    (directory / "ok.md").write_text("fine")

    templates = load_prompt_templates([directory])
    assert [t.name for t in templates] == ["ok"]


def test_render_prompt_template_replaces_variables() -> None:
    template = PromptTemplate(name="t", path=Path("/t.md"), content="Hi {{ name }}!")
    assert render_prompt_template(template, {"name": "world"}) == "Hi world!"


def test_render_prompt_template_rejects_missing_variables() -> None:
    template = PromptTemplate(name="t", path=Path("/t.md"), content="Hi {{ name }}!")
    with pytest.raises(ResourceError):
        render_prompt_template(template, {})


def test_render_prompt_template_blanks_missing_variables_with_fallback() -> None:
    template = PromptTemplate(name="t", path=Path("/t.md"), content="Hi {{ name }}!")
    assert render_prompt_template(template, {}, missing="") == "Hi !"


def test_expand_prompt_template_command_replaces_slash_command() -> None:
    template = PromptTemplate(
        name="brief",
        path=Path("/brief.md"),
        content="Prove {{ arguments }} thm.",
    )
    assert expand_prompt_template_command("/brief 2+2", [template]) == "Prove 2+2 thm."


def test_expand_prompt_template_command_blanks_missing_custom_variables() -> None:
    template = PromptTemplate(
        name="brief",
        path=Path("/brief.md"),
        content="Prove {{ statement }} quickly.",
    )
    assert expand_prompt_template_command("/brief", [template]) == "Prove  quickly."


def test_expand_prompt_template_command_appends_arguments_without_placeholder() -> None:
    template = PromptTemplate(
        name="brief",
        path=Path("/brief.md"),
        content="Prove it.",
    )
    assert expand_prompt_template_command("/brief 2+2", [template]) == "Prove it.\n\n2+2"


def test_expand_prompt_template_command_ignores_unknown_commands() -> None:
    template = PromptTemplate(name="brief", path=Path("/brief.md"), content="Prove it.")
    assert expand_prompt_template_command("/nope hi", [template]) is None
    assert expand_prompt_template_command("plain text", [template]) is None
    assert expand_prompt_template_command("//comment", [template]) is None


def test_is_prompt_template_candidate() -> None:
    assert is_prompt_template_candidate(Path("a.md"))
    assert is_prompt_template_candidate(Path("a.MD"))
    assert not is_prompt_template_candidate(Path("a.txt"))
    assert not is_prompt_template_candidate(Path("prompts.md"))
    assert not is_prompt_template_candidate(Path("reload.md"))