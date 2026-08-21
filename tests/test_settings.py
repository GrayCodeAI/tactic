"""agent.settings — layered settings.json + precedence tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent import settings


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    settings.clear_settings_cache()
    for key in settings.DEFAULTS:
        monkeypatch.delenv(settings.env_name(key), raising=False)
    yield
    settings.clear_settings_cache()


def _write_user_settings(tmp_path: Path, data: dict) -> Path:
    p = tmp_path / ".prover" / "settings.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data))
    return p


def test_builtin_defaults(monkeypatch, tmp_path) -> None:
    # No env, no files -> defaults. Point HOME at a fresh dir so nothing exists.
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.delenv("PROVER_CONFIG_DIR", raising=False)
    assert settings.get("max_steps") == 20
    assert settings.get("permission_mode") == "ask"
    assert settings.get("quiet") is False


def test_user_file_applies(monkeypatch, tmp_path) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.delenv("PROVER_CONFIG_DIR", raising=False)
    _write_user_settings(fake_home, {"max_steps": 7, "quiet": True})
    assert settings.get("max_steps") == 7
    assert settings.get("quiet") is True


def test_env_beats_file(monkeypatch, tmp_path) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.delenv("PROVER_CONFIG_DIR", raising=False)
    _write_user_settings(fake_home, {"max_steps": 7})
    monkeypatch.setenv("PROVER_MAX_STEPS", "11")
    assert settings.get("max_steps") == 11


def test_unknown_key_raises() -> None:
    with pytest.raises(KeyError):
        settings.get("bogus")


def test_canonical_key_normalises() -> None:
    assert settings.canonical_key("Max-Steps") == "max_steps"


def test_bad_file_ignored(monkeypatch, tmp_path) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.delenv("PROVER_CONFIG_DIR", raising=False)
    p = _write_user_settings(fake_home, "{not json")
    assert p.exists()
    # Malformed file must not crash; falls back to default.
    assert settings.get("max_steps") == 20


def test_explicit_path_override(monkeypatch, tmp_path) -> None:
    p = tmp_path / "alt.json"
    p.write_text(json.dumps({"workers": 5}))
    assert settings.get("workers") == 1
    assert settings.get("workers", path=p) == 5


def test_all_settings() -> None:
    res = settings.all_settings()
    assert set(res) == set(settings.DEFAULTS)
