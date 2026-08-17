"""Markdown prompt template loading and rendering.

Tau port (tau_coding/prompt_templates.py) with tau's resource-path
machinery flattened to tactic's `~/.tactic/prompts` + `<project>/.tactic/
prompts` namespaces (the project namespace wins).  Templates are markdown;
`{{ variable }}` placeholders render from arguments; the `/prompts` picker
and slash-expansion replicate tau's command behavior.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

_TEMPLATE_VARIABLE_RE = re.compile(r"{{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*}}")
_ARGUMENT_TEMPLATE_VARIABLES = {"arguments", "args"}
_RESERVED_TEMPLATE_NAMES = frozenset({"prompts", "skills", "tools", "reload"})

_DESCRIPTION_RE = re.compile(r"^description\s*:\s*(.+)$", re.MULTILINE)


class ResourceError(ValueError):
    """Raised when prompt templates are invalid or cannot be expanded."""


@dataclass(frozen=True, slots=True)
class ResourceDiagnostic:
    """A non-fatal resource discovery problem or precedence note."""

    kind: str
    message: str
    path: Path | None = None
    name: str | None = None
    severity: str = "warning"

    def format(self) -> str:
        """Return a concise human-readable diagnostic line."""
        parts = [self.severity, self.kind]
        if self.name is not None:
            parts.append(self.name)
        if self.path is not None:
            parts.append(str(self.path))
        return ": ".join(parts) + f": {self.message}"


@dataclass(frozen=True, slots=True)
class PromptTemplate:
    """A markdown prompt template resource."""

    name: str
    path: Path
    content: str
    description: str | None = None


def prompt_templates_dirs() -> list[Path]:
    """Return the prompt template namespaces, project highest precedence."""
    override = os.environ.get("TACTIC_PROMPTS_DIR")
    if override:
        return [Path(override)]
    from .tui import REPO

    return [Path.home() / ".tactic" / "prompts", REPO / ".tactic" / "prompts"]


def is_prompt_template_candidate(path: Path) -> bool:
    """Return whether a directory entry is eligible for prompt loading."""
    return path.suffix.lower() == ".md" and path.stem.casefold() not in _RESERVED_TEMPLATE_NAMES


def load_prompt_templates(
    prompts_dirs: Sequence[Path] | None = None,
) -> list[PromptTemplate]:
    """Load markdown prompt templates, project namespace winning."""
    templates, diagnostics = load_prompt_templates_with_diagnostics(prompts_dirs)
    if diagnostics:
        first = diagnostics[0]
        if first.severity == "error":
            raise ResourceError(first.message)
    return templates


def load_prompt_templates_with_diagnostics(
    prompts_dirs: Sequence[Path] | None = None,
) -> tuple[list[PromptTemplate], list[ResourceDiagnostic]]:
    """Load prompt templates and return non-fatal discovery diagnostics."""
    dirs = list(prompts_dirs) if prompts_dirs is not None else prompt_templates_dirs()
    templates_by_name: dict[str, PromptTemplate] = {}
    diagnostics: list[ResourceDiagnostic] = []
    for prompts_dir in dirs:
        try:
            entries = sorted(prompts_dir.glob("*.md")) if prompts_dir.is_dir() else ()
        except OSError as exc:
            diagnostics.append(
                ResourceDiagnostic(
                    kind="prompt",
                    message=f"unreadable prompts directory: {exc}",
                    path=prompts_dir,
                )
            )
            continue
        for path in entries:
            if not is_prompt_template_candidate(path):
                continue
            try:
                template = _load_prompt_template(path)
            except (OSError, UnicodeError) as exc:
                diagnostics.append(
                    ResourceDiagnostic(
                        kind="prompt",
                        message=f"could not read: {exc}",
                        path=path,
                        severity="error",
                    )
                )
                continue
            previous = templates_by_name.get(template.name)
            if previous is not None:
                diagnostics.append(
                    ResourceDiagnostic(
                        kind="prompt",
                        name=template.name,
                        path=template.path,
                        message=f"overrides lower-precedence resource at {previous.path}",
                    )
                )
            templates_by_name[template.name] = template
    return sorted(templates_by_name.values(), key=lambda template: template.name), diagnostics


def _load_prompt_template(path: Path) -> PromptTemplate:
    """Load a single markdown template with an optional `description:` line."""
    content = path.read_text(encoding="utf-8")
    description_match = _DESCRIPTION_RE.search(content)
    return PromptTemplate(
        name=path.stem,
        path=path,
        content=content,
        description=description_match.group(1).strip() if description_match else None,
    )


def render_prompt_template(
    template: PromptTemplate,
    variables: Mapping[str, str],
    *,
    missing: str | None = None,
) -> str:
    """Render a prompt template using `{{ variable }}` placeholders.

    By default, missing variables raise `ResourceError`. Callers that treat
    templates as user-facing shortcuts can pass `missing` to render absent
    variables as a fallback string instead.
    """

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        value = variables.get(name)
        if value is None:
            if missing is None:
                raise ResourceError(f"Missing prompt template variable: {name}")
            return missing
        return value

    return _TEMPLATE_VARIABLE_RE.sub(replace, template.content)


def expand_prompt_template_command(
    text: str,
    templates: Sequence[PromptTemplate],
) -> str | None:
    """Expand `/name [arguments]` text with a loaded prompt template.

    Template names are matched by markdown filename stem. Invocation arguments are
    available to templates as `{{ arguments }}` or `{{ args }}`. If a template has
    no placeholders, arguments are appended after a blank line.
    """
    stripped = text.strip()
    if not stripped.startswith("/") or stripped.startswith("//"):
        return None

    name, args = _parse_prompt_template_command(stripped)
    if not name:
        return None

    template = _find_prompt_template(name, templates)
    if template is None:
        return None

    rendered = render_prompt_template(
        template,
        {"arguments": args, "args": args},
        missing="",
    )
    if args and not _template_references_arguments(template.content):
        return f"{rendered.rstrip()}\n\n{args}"
    return rendered


def _template_references_arguments(content: str) -> bool:
    return any(
        match.group(1) in _ARGUMENT_TEMPLATE_VARIABLES
        for match in _TEMPLATE_VARIABLE_RE.finditer(content)
    )


def _find_prompt_template(
    name: str,
    templates: Sequence[PromptTemplate],
) -> PromptTemplate | None:
    normalized_name = name.strip().removeprefix("/").lower()
    for template in templates:
        if template.name.lower() == normalized_name:
            return template
    return None


def _parse_prompt_template_command(text: str) -> tuple[str, str]:
    command, separator, args = text[1:].partition(" ")
    return command.strip().lower(), args.strip() if separator else ""