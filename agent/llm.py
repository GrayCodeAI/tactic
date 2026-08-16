"""LLM provider — any OpenAI-compatible endpoint via env vars."""

from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

from openai import OpenAI

_client: OpenAI | None = None
_pool = ThreadPoolExecutor(max_workers=4)

# Hard wall-clock cap per LLM call. httpx read-timeouts reset on every byte
# received, so slow-streaming reasoning endpoints can hang forever without this.
HARD_TIMEOUT = float(os.environ.get("TACTIC_LLM_TIMEOUT", "180"))


def client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY", "unused"),
            base_url=os.environ.get("OPENAI_BASE_URL"),
            timeout=120.0,      # free tiers hang; fail fast and retry
            max_retries=2,
        )
    return _client


def model() -> str:
    return os.environ.get("TACTIC_MODEL", "gpt-4o")


def _call(system: str, messages: list[dict], temperature: float) -> str:
    resp = client().chat.completions.create(
        model=model(),
        messages=[{"role": "system", "content": system}, *messages],
        temperature=temperature,
        # NOTE: on reasoning endpoints max_tokens covers thinking + answer.
        # Too small = thinking eats the budget, content comes back empty.
        max_tokens=16384,
    )
    return resp.choices[0].message.content or ""


def chat(
    system: str,
    messages: list[dict],
    temperature: float = 0.2,
    retries: int = 4,
) -> str:
    """One LLM turn with a hard wall-clock cap and 429 backoff."""
    backoff = 5.0
    for attempt in range(retries + 1):
        fut = _pool.submit(_call, system, messages, temperature)
        try:
            return fut.result(timeout=HARD_TIMEOUT)
        except FuturesTimeout:
            fut.cancel()
            return f"[LLM error: hard timeout after {HARD_TIMEOUT:.0f}s]"
        except Exception as e:
            msg = str(e)
            is_rate = "429" in msg or "rate limit" in msg.lower()
            if is_rate and attempt < retries:
                time.sleep(backoff)
                backoff = min(backoff * 2, 60.0)
                continue
            return f"[LLM error: {msg}]"


def extract_lean_code(text: str) -> str:
    """Pull the first ```lean block out of a model reply, or return as-is."""
    import re

    m = re.search(r"```(?:lean)?\s*\n(.*?)```", text, re.DOTALL)
    return m.group(1).strip() if m else text.strip()
