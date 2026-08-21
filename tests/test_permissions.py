"""agent.permissions — per-tool ACL + stable IDs tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent.permissions import PermissionStore


def _store(tmp_path: Path) -> PermissionStore:
    return PermissionStore(path=tmp_path / "permissions.json")


def test_default_mode_is_ask(tmp_path) -> None:
    s = _store(tmp_path)
    assert s.mode == "ask"
    # ask baseline denies by default (explicit rule can still allow)
    assert s.check("prove_theorem") == "deny"


def test_mode_validation(tmp_path) -> None:
    s = _store(tmp_path)
    with pytest.raises(ValueError):
        s.mode = "nope"
    s.mode = "auto"
    assert s.check("anything") == "allow"
    s.mode = "yolo"
    assert s.check("anything") == "allow"


def test_rule_lookup_exact(tmp_path) -> None:
    s = _store(tmp_path)
    s.mode = "ask"
    s.add_rule("prove_theorem", "", allow=True)
    assert s.check("prove_theorem") == "allow"
    # unrelated tool still defaults to deny under ask
    assert s.check("other_tool") == "deny"


def test_rule_with_pattern(tmp_path) -> None:
    s = _store(tmp_path)
    s.mode = "ask"
    s.add_rule("prove_theorem", '"difficulty": "easy"', allow=True)
    assert s.check("prove_theorem", '{"difficulty": "easy"}') == "allow"
    assert s.check("prove_theorem", '{"difficulty": "hard"}') == "deny"


def test_most_specific_wins(tmp_path) -> None:
    s = _store(tmp_path)
    s.mode = "auto"
    s.add_rule("prove_theorem", "", allow=False)          # deny all
    s.add_rule("prove_theorem", "hard", allow=True)       # but allow hard
    assert s.check("prove_theorem", "hard problem") == "allow"
    assert s.check("prove_theorem", "easy problem") == "deny"


def test_stable_id_dedup(tmp_path) -> None:
    s = _store(tmp_path)
    rid1 = s.add_rule("prove_theorem", "", allow=True)
    rid2 = s.add_rule("prove_theorem", "", allow=False)  # same (tool, pattern)
    assert rid1 == rid2
    rule = s.get_rule(rid1)
    assert rule["tool"] == "prove_theorem"
    assert rule["allow"] is False


def test_remove_rule(tmp_path) -> None:
    s = _store(tmp_path)
    rid = s.add_rule("prove_theorem", "", allow=True)
    assert s.remove_rule(rid) is True
    assert s.remove_rule(rid) is False
    assert s.get_rule(rid) is None


def test_persist_roundtrip(tmp_path) -> None:
    path = tmp_path / "permissions.json"
    s = PermissionStore(path=path)
    s.mode = "auto"
    rid = s.add_rule("prove_theorem", "easy", allow=True, note="test")
    s.save()

    s2 = PermissionStore(path=path)
    assert s2.mode == "auto"
    assert s2.get_rule(rid)["note"] == "test"
    assert s2.check("prove_theorem", "easy") == "allow"


def test_missing_store_is_fresh(tmp_path) -> None:
    s = _store(tmp_path)
    assert s.rules() == {}
    assert s.check("x") == "deny"


def test_requires_tool_name(tmp_path) -> None:
    s = _store(tmp_path)
    with pytest.raises(ValueError):
        s.add_rule("   ", "", allow=True)


# --------------------------------------------------------------------------- MCP gating


def test_acl_denies_blocks_mcp_tool(monkeypatch, tmp_path) -> None:
    """An explicit deny rule blocks an MCP tool call; open by default otherwise."""
    from agent import mcp

    monkeypatch.setenv("PROVER_CONFIG_DIR", str(tmp_path))
    store = PermissionStore(path=tmp_path / "permissions.json")
    store.add_rule("prove_theorem", "", allow=False)
    store.save()
    assert mcp._acl_denies("prove_theorem", {"statement": "theorem t : True := by trivial"}) is True
    assert mcp._acl_denies("problems", {}) is False


def test_acl_denies_open_by_default(monkeypatch, tmp_path) -> None:
    from agent import mcp

    monkeypatch.setenv("PROVER_CONFIG_DIR", str(tmp_path))
    assert mcp._acl_denies("prove_theorem", {}) is False


def test_acl_denies_pattern_match(monkeypatch, tmp_path) -> None:
    from agent import mcp

    monkeypatch.setenv("PROVER_CONFIG_DIR", str(tmp_path))
    store = PermissionStore(path=tmp_path / "permissions.json")
    store.add_rule("prove_theorem", "hard", allow=False)
    store.save()
    assert mcp._acl_denies("prove_theorem", {"statement": "a hard theorem"}) is True
    assert mcp._acl_denies("prove_theorem", {"statement": "an easy tree"}) is False


def test_acl_denies_never_crashes_server(monkeypatch, tmp_path) -> None:
    from agent import mcp

    # A corrupt store must not raise through the MCP gate.
    permissions = tmp_path / "permissions.json"
    permissions.parent.mkdir(parents=True, exist_ok=True)
    permissions.write_text("{not valid json]")
    monkeypatch.setenv("PROVER_CONFIG_DIR", str(tmp_path))
    assert mcp._acl_denies("prove_theorem", {}) is False
