from __future__ import annotations

PROVIDER_CATALOG: dict[str, dict] = {
    "openai": {"base_url": "https://api.openai.com/v1", "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"]},
    "anthropic": {"base_url": "https://api.anthropic.com/v1", "models": ["claude-3-5-sonnet", "claude-3-opus"], "note": "use openai-compatible proxy via openrouter"},
    "google": {"base_url": "https://generativelanguage.googleapis.com/v1", "models": ["gemini-1.5-pro", "gemini-2.0-flash"]},
    "mistral": {"base_url": "https://api.mistral.ai/v1", "models": ["mistral-large", "mistral-small"]},
    "deepseek": {"base_url": "https://api.deepseek.com/v1", "models": ["deepseek-chat", "deepseek-prover"]},
    "qwen": {"base_url": None, "models": ["qwen/qwen3-8b", "Qwen/Qwen3-27B"]},
}


def provider_for_model(model: str) -> str | None:
    m = model.lower()
    for prov, info in PROVIDER_CATALOG.items():
        for pat in info["models"]:
            if m.startswith(pat.lower()) or pat.lower() in m:
                return prov
    return None
