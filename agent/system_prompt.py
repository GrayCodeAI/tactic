"""System prompt builder — Tau system_prompt.py port, lean-adapted.

Builds the system prompt from tools, skills, context files, custom prompt
overrides, and extra guidelines.  The lean prover has its own hardcoded
``SYSTEM`` constant in ``prover_loop.py``; this builder is used by the
``CodingSession`` path.
"""

from __future__ import annotations

from typing import Any


def build_system_prompt(
    tools: list | None = None,
    skills: list | None = None,
    custom_prompt: str | None = None,
    append_system_prompt: str | None = None,
    context_files: list[dict[str, str]] | None = None,
    extra_guidelines: str | None = None,
) -> str:
    """Build a system prompt from its components (tau BuildSystemPromptOptions)."""
    parts: list[str] = []

    if custom_prompt:
        parts.append(custom_prompt)
    else:
        parts.append("You are a helpful coding agent.")

    if context_files:
        for file in context_files:
            path = file.get("path", "?")
            content = file.get("content", "")
            if content:
                parts.append(f"<context file=\"{path}\">\n{content}\n</context>")

    if skills:
        parts.append(format_skills_for_prompt(skills))

    if extra_guidelines:
        parts.append(extra_guidelines)

    if append_system_prompt:
        parts.append(append_system_prompt)

    return "\n\n".join(parts)


def format_skills_for_prompt(skills: list[Any]) -> str:
    """Format discovered skills for the system prompt (tau format_skills_for_prompt)."""
    lines = ["## Available Skills"]
    for skill in skills:
        name = getattr(skill, "name", str(skill))
        desc = getattr(skill, "description", "")
        lines.append(f"- **{name}**: {desc}")
    return "\n".join(lines)