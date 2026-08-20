from __future__ import annotations


def provider_http_error_message(status: int, body: str) -> str:
    return f"HTTP {status}: {body[:500]}"
