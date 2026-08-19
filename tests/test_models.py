"""Unit tests for model profiles (agent/models.py + llm.py integration).

Model profile config is fully offline: the store is a JSON file under the
config dir, and client construction never touches the network.
"""

from __future__ import annotations

import pytest

from agent import llm, models
from agent.models import ModelProfile


@pytest.fixture
def isolated_config(monkeypatch, tmp_path) -> None:
    """Point the profile store at a temp dir and clear env overrides."""
    monkeypatch.setenv("PROVER_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.delenv("PROVER_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("PROVER_CONTEXT_WINDOW", raising=False)


@pytest.fixture
def two_profiles(isolated_config) -> list[ModelProfile]:
    profiles = [
        ModelProfile(name="qwen-27b", label="Qwen 27B",
                     base_url="http://profile-test/v1", api_key="profile-key",
                     context_window=262_144, cost_in=5.0, cost_out=15.0),
        ModelProfile(name="deepseek-r1", base_url=""),
    ]
    models.save_store(active="qwen-27b", profiles=profiles)
    return profiles


def test_save_load_roundtrip(isolated_config) -> None:
    models.save_store(active="a", profiles=[
        ModelProfile(name="a", label="A", base_url="http://x/v1", api_key="k",
                     context_window=64_000, cost_in=0.1, cost_out=0.2),
    ])
    loaded = models.load_profiles()
    assert len(loaded) == 1
    p = loaded[0]
    assert (p.name, p.label, p.base_url, p.api_key) == ("a", "A", "http://x/v1", "k")
    assert (p.context_window, p.cost_in, p.cost_out) == (64_000, 0.1, 0.2)


def test_load_missing_file_returns_empty(isolated_config) -> None:
    assert models.load_profiles() == []


def test_load_corrupt_file_returns_empty(isolated_config, monkeypatch) -> None:
    path = models.models_store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json", encoding="utf-8")
    assert models.load_profiles() == []


def test_resolved_model_name_defaults(isolated_config) -> None:
    assert models.resolved_model_name() == models.DEFAULT_MODEL


def test_resolved_model_name_uses_store_active(two_profiles) -> None:
    assert models.resolved_model_name() == "qwen-27b"


def test_resolved_model_name_env_wins(two_profiles, monkeypatch) -> None:
    monkeypatch.setenv("PROVER_MODEL", "gpt-4o")
    assert models.resolved_model_name() == "gpt-4o"


def test_profile_for_by_name(two_profiles) -> None:
    assert models.profile_for("deepseek-r1").name == "deepseek-r1"
    assert models.profile_for("missing") is None


def test_active_profile_matches_store(two_profiles) -> None:
    profile = models.active_profile()
    assert profile is not None
    assert profile.name == "qwen-27b"
    assert profile.base_url == "http://profile-test/v1"


def test_active_profile_env_match_wins(two_profiles, monkeypatch) -> None:
    monkeypatch.setenv("PROVER_MODEL", "deepseek-r1")
    profile = models.active_profile()
    assert profile is not None
    assert profile.name == "deepseek-r1"


def test_llm_model_uses_active_profile(two_profiles) -> None:
    assert llm.model() == "qwen-27b"


def test_llm_model_env_still_wins(two_profiles, monkeypatch) -> None:
    monkeypatch.setenv("PROVER_MODEL", "gpt-4o")
    assert llm.model() == "gpt-4o"


def test_client_uses_profile_endpoint(two_profiles) -> None:
    client = llm.client()
    assert client.api_key == "profile-key"
    assert "profile-test" in str(client.base_url)


def test_client_falls_back_to_env_endpoint(isolated_config, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_BASE_URL", "http://env-endpoint/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")
    client = llm.client()
    assert client.api_key == "env-key"
    assert "env-endpoint" in str(client.base_url)


def test_context_window_profile_override(two_profiles) -> None:
    assert llm.context_window_tokens("qwen-27b") == 262_144


def test_context_window_env_override_wins(two_profiles, monkeypatch) -> None:
    monkeypatch.setenv("PROVER_CONTEXT_WINDOW", "9999")
    assert llm.context_window_tokens("qwen-27b") == 9999


def test_context_window_falls_back_to_table(isolated_config) -> None:
    assert llm.context_window_tokens("gpt-4o") == 128_000


def test_estimate_cost_profile_override(two_profiles) -> None:
    # 1000 prompt @ $5 + 1000 completion @ $15 = $0.02
    assert llm.estimate_cost(1000, 1000, "qwen-27b") == pytest.approx(0.02)


def test_estimate_cost_partial_profile_overrides_falls_back(isolated_config) -> None:
    models.save_store(active="partial", profiles=[
        ModelProfile(name="partial", cost_in=1.0, cost_out=None),
    ])
    # cost_out missing -> no profile override, table has no entry -> free
    assert llm.estimate_cost(1000, 1000, "partial") == 0.0


def test_available_models_empty_without_any_endpoint(isolated_config) -> None:
    assert llm.available_models() == []
