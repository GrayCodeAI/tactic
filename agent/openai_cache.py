from __future__ import annotations


def is_direct_openai_url(url: str | None) -> bool:
    return url is not None and "api.openai.com" in url


def openai_prompt_cache_key(session_id: str | None) -> str | None:
    return session_id
