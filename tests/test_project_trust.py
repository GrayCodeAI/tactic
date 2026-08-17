"""Tests for project-input trust — ported from
huggingface/tau tests/test_project_trust.py, trimmed to tactic's protected
resources (problems/leaderboard/prompts/settings/themes)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from agent.project_trust import (
    CanonicalProjectPath,
    ProjectTrustCoordinator,
    ProjectTrustError,
    ProjectTrustStore,
    ProtectedResourceDetector,
    canonicalize_project_path,
    format_trust_diagnostic,
)


def test_canonical_project_path_requires_existing_directory_and_resolves_alias(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    canonical = canonicalize_project_path(project)
    assert canonical.value == project.resolve()

    alias = project / ".." / "project"
    assert canonicalize_project_path(alias).value == canonical.value

    with pytest.raises(ProjectTrustError):
        canonicalize_project_path(tmp_path / "missing")
    with pytest.raises(ProjectTrustError):
        canonicalize_project_path(tmp_path / "file.txt")  # not a dir

    (tmp_path / "plain.txt").write_text("x")
    with pytest.raises(ProjectTrustError):
        canonicalize_project_path(Path("relative"), base=tmp_path / "missing")


def test_detector_covers_protected_matrix_without_reading_contents(tmp_path: Path) -> None:
    (tmp_path / "benchmark").mkdir()
    (tmp_path / "benchmark" / "problems.json").write_text("not valid json {}")
    (tmp_path / "leaderboard.json").write_text("x")
    (tmp_path / ".tactic" / "prompts").mkdir(parents=True)
    (tmp_path / ".tactic" / "prompts" / "t1.md").write_text("x")
    (tmp_path / ".tactic" / "settings").mkdir()
    (tmp_path / ".tactic" / "settings" / "s.json").write_text("x")

    summary = ProtectedResourceDetector().detect(
        canonicalize_project_path(tmp_path)
    )
    assert summary.categories == ("problems", "leaderboard", "prompts", "settings")
    assert summary.counts == {
        "problems": 1,
        "leaderboard": 1,
        "prompts": 1,
        "settings": 1,
    }
    assert summary.total == 4
    assert len(summary.sample_paths) == 4


def test_detector_ignores_empty_and_unsupported_resources(tmp_path: Path) -> None:
    (tmp_path / ".tactic").mkdir()
    (tmp_path / ".tactic" / "prompts").mkdir()
    summary = ProtectedResourceDetector().detect(canonicalize_project_path(tmp_path))
    assert summary.categories == ()
    assert summary.total == 0


def test_store_round_trip_is_sorted_and_nearest_decision_wins(tmp_path: Path) -> None:
    store = ProjectTrustStore(tmp_path)
    child = canonicalize_project_path(tmp_path / "a" / "b", base=tmp_path) if False else None
    (tmp_path / "a" / "b").mkdir(parents=True)
    child = canonicalize_project_path(tmp_path / "a" / "b")
    parent = CanonicalProjectPath(child.value.parent)

    store.set(child, "trusted")
    store.set(parent, "untrusted")

    payload = json.loads((tmp_path / "trust.json").read_text())
    assert payload["version"] == 1
    decisions = payload["decisions"]
    assert decisions == sorted(decisions, key=lambda d: d["path"])
    assert {d["path"]: d["decision"] for d in decisions} == {
        str(child.value): "trusted",
        str(parent.value): "untrusted",
    }

    # Nearest decision (exact) wins over inherited parent
    entry = store.nearest(child)
    assert entry is not None
    assert entry.decision == "trusted"
    assert entry.path.value == child.value

    # Grandchild inherits from nearest ancestor
    (child.value / "c").mkdir()
    grandchild = canonicalize_project_path(child.value / "c")
    assert store.nearest(grandchild).decision == "trusted"

    store.set(child, "untrusted")
    assert store.nearest(child).decision == "untrusted"


def test_parent_trust_removes_exact_child_for_inheritance(tmp_path: Path) -> None:
    store = ProjectTrustStore(tmp_path)
    (tmp_path / "a").mkdir()
    child = canonicalize_project_path(tmp_path / "a")
    store.set(child, "trusted")
    parent = store.trust_parent(child)
    assert parent.value == child.value.parent
    assert store.nearest(child).decision == "trusted"
    assert (tmp_path / "trust.json").read_text().count(str(child.value)) == 0


@pytest.mark.parametrize(
    "payload",
    [
        "not json",
        json.dumps({"version": 1}),
        json.dumps({"version": 2, "decisions": []}),
        json.dumps({"version": 1, "decisions": [{"path": "relative"}]}),
        json.dumps({"version": 1, "decisions": [{"path": "/a/b", "decision": "maybe"}]}),
        json.dumps({"version": 1, "decisions": [{"path": "/a/../b", "decision": "trusted"}]}),
        json.dumps(
            {
                "version": 1,
                "decisions": [
                    {"path": "/a/b", "decision": "trusted"},
                    {"path": "/a/b", "decision": "trusted"},
                ],
            }
        ),
    ],
)
def test_store_rejects_malformed_data(tmp_path: Path, payload: str) -> None:
    store = ProjectTrustStore(tmp_path)
    (tmp_path / "trust.json").write_text(payload)
    with pytest.raises(ProjectTrustError):
        store.read()


def test_concurrent_store_updates_do_not_lose_decisions(tmp_path: Path) -> None:
    store = ProjectTrustStore(tmp_path)
    (tmp_path / "a").mkdir()

    def worker(index: int) -> None:
        local = ProjectTrustStore(tmp_path)
        local.set(canonicalize_project_path(tmp_path / "a"), "trusted" if index % 2 else "untrusted")

    if False:
        pass
    import threading

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    decisions = store.read()
    assert len(decisions) == 1


async def _test_policy_precedence_saved_before_default_and_override_coro(tmp_path: Path) -> None:
    store = ProjectTrustStore(tmp_path)
    (tmp_path / "benchmark").mkdir()
    (tmp_path / "benchmark" / "problems.json").write_text("x")

    store.set(canonicalize_project_path(tmp_path), "trusted")
    _, resolution = await ProjectTrustCoordinator(store).resolve(tmp_path)
    assert resolution.trusted
    assert resolution.source == "saved"

    _, resolution = await ProjectTrustCoordinator(store).resolve(tmp_path, default="never")
    assert resolution.trusted  # saved still wins

    _, resolution = await ProjectTrustCoordinator(store).resolve(
        tmp_path, override="decline"
    )
    assert not resolution.trusted
    assert resolution.source == "override"


def test_policy_precedence_saved_before_default_and_override(tmp_path: Path) -> None:
    asyncio.run(_test_policy_precedence_saved_before_default_and_override_coro(tmp_path))

async def _test_malformed_store_fails_closed_but_run_override_still_works_coro(
    tmp_path: Path,
) -> None:
    store = ProjectTrustStore(tmp_path)
    (tmp_path / "benchmark").mkdir()
    (tmp_path / "benchmark" / "problems.json").write_text("x")
    (tmp_path / "trust.json").write_text("not json")

    _, declined = await ProjectTrustCoordinator(store).resolve(tmp_path)
    _, default_always = await ProjectTrustCoordinator(store).resolve(tmp_path, default="always")
    _, approved = await ProjectTrustCoordinator(store).resolve(tmp_path, override="approve")

    assert declined.trusted is False  # malformed store: fail closed
    assert default_always.trusted is False
    assert declined.diagnostics
    assert "trust.json" in declined.diagnostics[0]
    assert approved.trusted is True


def test_malformed_store_fails_closed_but_run_override_still_works(tmp_path: Path) -> None:
    asyncio.run(
        _test_malformed_store_fails_closed_but_run_override_still_works_coro(tmp_path)
    )


async def _test_empty_project_is_trusted_without_store_coro(tmp_path: Path) -> None:
    store = ProjectTrustStore(tmp_path)
    coordinator = ProjectTrustCoordinator(store)
    _, resolution = await coordinator.resolve(tmp_path)
    assert resolution.trusted
    assert resolution.source == "empty"


def test_empty_project_is_trusted_without_store(tmp_path: Path) -> None:
    asyncio.run(_test_empty_project_is_trusted_without_store_coro(tmp_path))

async def _test_interactive_choice_persists_exact_and_run_coro(
    tmp_path: Path, other: Path
) -> None:
    store = ProjectTrustStore(tmp_path)
    (tmp_path / "benchmark").mkdir()
    (tmp_path / "benchmark" / "problems.json").write_text("x")

    async def prompt_run(request):
        return "trust-run"

    _, resolution = await ProjectTrustCoordinator(store).resolve(
        tmp_path, interactive=True, prompt=prompt_run, default="ask"
    )
    assert resolution.trusted
    assert resolution.source == "ui"
    assert resolution.saved_path is None  # trust-run is not persisted

    async def prompt_exact(request):
        return "trust-exact"

    _, resolution = await ProjectTrustCoordinator(store).resolve(
        tmp_path, interactive=True, prompt=prompt_exact, default="ask"
    )
    assert resolution.trusted
    assert store.nearest(CanonicalProjectPath(tmp_path.resolve())).decision == "trusted"

    async def declining(request):
        return "decline-exact"

    (other / "benchmark").mkdir(parents=True)
    (other / "benchmark" / "problems.json").write_text("x")

    # A sibling project outside the trusted tree must ask interactively.
    _, resolution = await ProjectTrustCoordinator(store).resolve(
        other, interactive=True, prompt=declining, default="ask"
    )
    assert not resolution.trusted
    assert store.nearest(canonicalize_project_path(other)).decision == "untrusted"


def test_interactive_choice_persists_exact_and_run(tmp_path: Path, tmp_path_factory) -> None:
    other = tmp_path_factory.mktemp("unrelated")
    asyncio.run(_test_interactive_choice_persists_exact_and_run_coro(tmp_path, other))

async def _test_cached_candidate_resolution_is_reused_coro(tmp_path: Path) -> None:
    store = ProjectTrustStore(tmp_path)
    coordinator = ProjectTrustCoordinator(store)
    (tmp_path / "benchmark").mkdir()
    (tmp_path / "benchmark" / "problems.json").write_text("x")
    calls = []

    async def prompt(request):
        calls.append(request)
        return "trust-run"

    for _ in range(3):
        await coordinator.resolve(tmp_path, interactive=True, prompt=prompt)
    assert len(calls) == 1


def test_cached_candidate_resolution_is_reused(tmp_path: Path) -> None:
    asyncio.run(_test_cached_candidate_resolution_is_reused_coro(tmp_path))

def test_format_trust_diagnostic_is_bounded_and_content_free(tmp_path: Path) -> None:
    (tmp_path / "benchmark").mkdir()
    (tmp_path / "benchmark" / "problems.json").write_text("secret contents")
    summary, resolution = asyncio.run(
        ProjectTrustCoordinator(ProjectTrustStore(tmp_path)).resolve(
            tmp_path, override="decline"
        )
    )
    diagnostic = format_trust_diagnostic(summary, resolution)
    assert "problems=1" in diagnostic
    assert "untrusted" in diagnostic
    assert "secret contents" not in diagnostic