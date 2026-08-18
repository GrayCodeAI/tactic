"""ProverPaths env/precedence tests — ported from tau test_paths.py shape."""

from __future__ import annotations

from pathlib import Path

from agent.paths import ProverPaths


def test_defaults_use_dot_prover_in_home(monkeypatch: Path, tmp_path: Path) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.delenv("PROVER_CONFIG_DIR", raising=False)
    p = ProverPaths()
    assert p.config_dir == fake_home / ".prover"
    assert p.sessions_dir == fake_home / ".prover" / "sessions"
    assert p.prompts_dir == fake_home / ".prover" / "prompts"
    assert p.themes_dir == fake_home / ".prover" / "themes"


def test_config_dir_override_reshapes_all_subdirs(monkeypatch: Path, tmp_path: Path) -> None:
    monkeypatch.setenv("PROVER_CONFIG_DIR", str(tmp_path / "config"))
    p = ProverPaths()
    assert p.config_dir == tmp_path / "config"
    assert p.prompts_dir == tmp_path / "config" / "prompts"
    assert p.themes_dir == tmp_path / "config" / "themes"


def test_per_resource_env_overrides_win(monkeypatch: Path, tmp_path: Path) -> None:
    monkeypatch.setenv("PROVER_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("PROVER_PROMPTS_DIR", str(tmp_path / "custom-prompts"))
    monkeypatch.setenv("PROVER_THEMES_DIR", str(tmp_path / "custom-themes"))
    monkeypatch.setenv("PROVER_SESSIONS_DIR", str(tmp_path / "custom-sessions"))
    monkeypatch.setenv("PROVER_LOGS_DIR", str(tmp_path / "custom-logs"))
    p = ProverPaths()
    assert p.prompts_dir == tmp_path / "custom-prompts"
    assert p.themes_dir == tmp_path / "custom-themes"
    assert p.sessions_dir == tmp_path / "custom-sessions"
    assert p.logs_dir == tmp_path / "custom-logs"


def test_sessions_dir_does_not_follow_config_dir(monkeypatch: Path, tmp_path: Path) -> None:
    monkeypatch.setenv("PROVER_CONFIG_DIR", str(tmp_path / "config"))
    p = ProverPaths()
    assert p.sessions_dir == p.home / "sessions"


def test_project_over_user_precedence_for_prompts(monkeypatch: Path, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    p = ProverPaths()
    assert p.prompts_dir == p.config_dir / "prompts"
    assert p.project_prompts_dir == tmp_path / ".prover" / "prompts"


def test_home_override_is_independent(monkeypatch: Path, tmp_path: Path) -> None:
    monkeypatch.setenv("PROVER_CONFIG_DIR", str(tmp_path / "alt-config"))
    p = ProverPaths()
    assert p.sessions_dir == p.home / "sessions"
    assert p.sessions_dir != tmp_path / "alt-config" / "sessions"