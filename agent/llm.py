"""LLM provider — any OpenAI-compatible endpoint via env vars."""

from __future__ import annotations

import os

from openai import OpenAI

_client: OpenAI | None = None


def client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY", "unused"),
            base_url=os.environ.get("OPENAI_BASE_URL"),
        )
    return _client


def model() -> str:
    return os.environ.get("TACTIC_MODEL", "gpt-4o")


def chat(system: str, messages: list[dict], temperature: float = 0.2) -> str:
    resp = client().chat.completions.create(
        model=model(),
        messages=[{"role": "system", "content": system}, *messages],
        temperature=temperature,
    )
    return resp.choices[0].message.content or ""


def extract_lean_code(text: str) -> str:
    """Pull the first ```lean block out of a model reply, or return as-is."""
    import re

    m = re.search(r"```(?:lean)?\s*\n(.*?)```", text, re.DOTALL)
    return m.group(1).strip() if m else text.strip()
