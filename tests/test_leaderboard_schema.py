"""leaderboard.json schema validation — keeps the public site from breaking."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REQUIRED_TOP_LEVEL = {"name", "score", "total", "tiers", "max_steps", "date"}
REQUIRED_TIER = {"proved", "total"}
ALLOWED_TIER_NAMES = {"trivial", "easy", "medium", "hard"}


@pytest.fixture(scope="module")
def board():
    return json.loads(Path("leaderboard.json").read_text())


def test_board_is_a_list(board) -> None:
    assert isinstance(board, list)


def test_entries_have_required_fields(board) -> None:
    for entry in board:
        missing = REQUIRED_TOP_LEVEL - set(entry)
        assert not missing, f"entry {entry.get('name')!r} missing fields: {missing}"


def test_scores_are_consistent(board) -> None:
    for entry in board:
        tier_sum = sum(t["proved"] for t in entry["tiers"].values())
        assert entry["score"] == tier_sum, (
            f"{entry['name']}: score {entry['score']} != tier sum {tier_sum}"
        )
        total_sum = sum(t["total"] for t in entry["tiers"].values())
        assert entry["total"] == total_sum, (
            f"{entry['name']}: total {entry['total']} != tier total sum {total_sum}"
        )


def test_tier_proved_within_total(board) -> None:
    for entry in board:
        for tier, counts in entry["tiers"].items():
            assert set(counts) >= REQUIRED_TIER, f"{entry['name']}/{tier} shape"
            assert 0 <= counts["proved"] <= counts["total"], (
                f"{entry['name']}/{tier}: proved {counts['proved']} out of range"
            )
        assert set(entry["tiers"]) <= ALLOWED_TIER_NAMES, (
            f"{entry['name']} has unknown tier names"
        )


def test_names_unique(board) -> None:
    names = [entry["name"] for entry in board]
    assert len(names) == len(set(names)), "duplicate leaderboard entries"


def test_max_steps_is_positive(board) -> None:
    for entry in board:
        assert isinstance(entry["max_steps"], int) and entry["max_steps"] >= 1
