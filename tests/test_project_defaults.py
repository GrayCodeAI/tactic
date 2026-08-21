"""agent.project_defaults — repo-safe .prover.json whitelist tests."""

from __future__ import annotations

import json

from agent import project_defaults as pd


def test_empty_dir_has_no_defaults(tmp_path) -> None:
    allowed, warnings = pd.load_project_defaults(cwd=tmp_path)
    assert allowed == {}
    assert warnings == []


def test_allowed_keys_kept(tmp_path) -> None:
    p = tmp_path / ".prover.json"
    p.write_text(json.dumps({"max_steps": 9, "context_window": 4096, "quiet": True}))
    allowed, warnings = pd.load_project_defaults(cwd=tmp_path)
    assert allowed == {"max_steps": 9, "context_window": 4096, "quiet": True}
    assert warnings == []


def test_forbidden_keys_dropped(tmp_path) -> None:
    p = tmp_path / ".prover.json"
    p.write_text(json.dumps({
        "max_steps": 5,
        "model": "gpt-4o",
        "api_key": "sk-secret",
        "permission": "yolo",
    }))
    allowed, warnings = pd.load_project_defaults(cwd=tmp_path)
    assert allowed == {"max_steps": 5}
    assert any("api_key" in w for w in warnings)
    assert any("model" in w for w in warnings)
    assert any("permission" in w for w in warnings)


def test_unknown_key_dropped(tmp_path) -> None:
    p = tmp_path / ".prover.json"
    p.write_text(json.dumps({"nonsense": 1}))
    allowed, warnings = pd.load_project_defaults(cwd=tmp_path)
    assert allowed == {}
    assert warnings and "nonsense" in warnings[0]


def test_wrong_type_dropped(tmp_path) -> None:
    p = tmp_path / ".prover.json"
    p.write_text(json.dumps({"max_steps": "many"}))
    allowed, warnings = pd.load_project_defaults(cwd=tmp_path)
    assert allowed == {}
    assert warnings and "max_steps" in warnings[0]


def test_non_object_ignored(tmp_path) -> None:
    p = tmp_path / ".prover.json"
    p.write_text(json.dumps([1, 2, 3]))
    allowed, warnings = pd.load_project_defaults(cwd=tmp_path)
    assert allowed == {}
    assert warnings


def test_env_path_wins(tmp_path, monkeypatch) -> None:
    p = tmp_path / "custom.json"
    p.write_text(json.dumps({"workers": 3}))
    monkeypatch.setenv("PROVER_PROJECT_CONFIG", str(p))
    allowed, _ = pd.load_project_defaults(cwd=tmp_path / "repo")
    assert allowed == {"workers": 3}


def test_effective_defaults_merge(tmp_path) -> None:
    p = tmp_path / ".prover.json"
    p.write_text(json.dumps({"max_steps": 8}))
    merged = pd.effective_defaults(cwd=tmp_path)
    assert merged["max_steps"] == 8
    assert merged["permission_mode"] == "ask"  # built-in floor preserved
