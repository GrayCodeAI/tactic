from __future__ import annotations

import httpx


def create_async_client(timeout: float = 60.0) -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=timeout)
