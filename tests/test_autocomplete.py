"""Slash-command autocomplete — ported from huggingface/tau tests/test_tui_autocomplete.py.

Tau completes command names, aliases, and search terms; direct-name matches
rank above search-term matches, ties broken by display name — we port that
ordering contract for tactic's slash-command surface.
"""

from __future__ import annotations

from agent.autocomplete import command_completions
from agent.commands import create_default_command_registry


def _names(items: list[tuple[str, str]]) -> list[str]:
    return [cmd for cmd, _ in items]


def test_no_completions_for_non_slash_input():
    registry = create_default_command_registry()
    assert command_completions(registry, "hello") == []
    assert command_completions(registry, "") == []


def test_no_completions_after_command_with_arguments():
    registry = create_default_command_registry()
    assert command_completions(registry, "/prove theorem ") == []
    assert command_completions(registry, "/workers 4") == []


def test_empty_slash_lists_all_commands_sorted():
    registry = create_default_command_registry()
    items = command_completions(registry, "/", max_items=100)
    names = _names(items)
    assert "/prove" in names
    assert "/quit" in names
    assert "/help" in names
    # tau's sort key: direct matches in display order
    direct = [n for n in names]
    assert direct == sorted(set(direct))


def test_partial_prefix_matches_command_names():
    registry = create_default_command_registry()
    assert _names(command_completions(registry, "/prov")) == ["/prove"]


def test_partial_prefix_matches_aliases_too():
    registry = create_default_command_registry()
    # /e matches /export (name) and /exit (alias of /quit); display order
    names = _names(command_completions(registry, "/e"))
    assert "/export" in names
    assert "/exit" in names
    assert names == sorted(names)


def test_aliased_matches_carry_alias_description():
    registry = create_default_command_registry()
    items = dict(command_completions(registry, "/exi"))
    assert items["/exit"] == "alias of /quit"


def test_search_term_completion_falls_back_to_canonical_name():
    registry = create_default_command_registry()
    # "parallel" is a search term for /workers
    assert _names(command_completions(registry, "/parallel")) == ["/workers"]


def test_search_terms_rank_after_direct_names():
    registry = create_default_command_registry()
    # "/r": direct matches /reload, /resume, /run; "/prove" arrives later
    # via the "run theorem" search term
    names = _names(command_completions(registry, "/r"))
    assert names[:3] == ["/reload", "/resume", "/run"]
    assert "/prove" in names


def test_max_items_respected():
    registry = create_default_command_registry()
    assert len(command_completions(registry, "/", max_items=3)) == 3


def test_case_insensitive_prefix():
    registry = create_default_command_registry()
    assert _names(command_completions(registry, "/PROV")) == ["/prove"]


def test_leading_whitespace_is_tolerated():
    registry = create_default_command_registry()
    assert _names(command_completions(registry, "  /stop")) == ["/stop"]
