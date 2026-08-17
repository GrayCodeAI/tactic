"""TacticPaths env/precedence tests — ported from tau test_paths.py shape."""

from __future__ import annotations

from pathlib import Path

from agent.paths import TacticPaths


def test_defaults_use_dot_tactic_in_home(monkeypatch: Path, tmp_path: Path) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.delenv("TACTIC_CONFIG_DIR", raising=False)
    p = TacticPaths()
    assert p.config_dir == fake_home / ".tactic"
    assert p.sessions_dir == fake_home / ".tactic" / "sessions"
    assert p.prompts_dir == fake_home / ".tactic" / "prompts"
    assert p.themes_dir == fake_home / ".tactic" / "themes"


def test_config_dir_override_reshapes_all_subdirs(monkeypatch: Path, tmp_path: Path) -> None:
    monkeypatch.setenv("TACTIC_CONFIG_DIR", str(tmp_path / "config"))
    p = TacticPaths()
    assert p.config_dir == tmp_path / "config"
    assert p.prompts_dir == tmp_path / "config" / "prompts"
    assert p.themes_dir == tmp_path / "config" / "themes"


def test_per_resource_env_overrides_win(monkeypatch: Path, tmp_path: Path) -> None:
    monkeypatch.setenv("TACTIC_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("TACTIC_PROMPTS_DIR", str(tmp_path / "custom-prompts"))
    monkeypatch.setenv("TACTIC_THEMES_DIR", str(tmp_path / "custom-themes"))
    monkeypatch.setenv("TACTIC_SESSIONS_DIR", str(tmp_path / "custom-sessions"))
    monkeypatch.setenv("TACTIC_LOGS_DIR", str(tmp_path / "custom-logs"))
    p = TacticPaths()
    assert p.prompts_dir == tmp_path / "custom-prompts"
    assert p.themes_dir == tmp_path / "custom-themes"
    assert p.sessions_dir == tmp_path / "custom-sessions"
    assert p.logs_dir == tmp_path / "custom-logs"


def test_sessions_dir_does_not_follow_config_dir(monkeypatch: Path, tmp_path: Path) -> None:
    monkeypatch.setenv("TACTIC_CONFIG_DIR", str(tmp_path / "config"))
    p = TacticPaths()
    assert p.sessions_dir == p.home / "sessions"


def test_project_over_user_precedence_for_prompts(monkeypatch: Path, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    p = TacticPaths()
    assert p.prompts_dir == p.config_dir / "prompts"
    assert p.project_prompts_dir == tmp_path / ".tactic" / "prompts"


def test_home_override_is_independent(monkeypatch: Path, tmp_path: Path) -> None:
    monkeypatch.setenv("TACTIC_CONFIG_DIR", str(tmp_path / "alt-config"))
    p = TacticPaths()
    assert p.sessions_dir == p.home / "sessions"
    assert p.sessions_dir != tmp_path / "alt-config" / "sessions"