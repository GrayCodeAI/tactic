"""LLM provider — any OpenAI-compatible endpoint via env vars."""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass

from openai import OpenAI

_client: OpenAI | None = None

# Hard wall-clock cap per LLM call. httpx read-timeouts reset on every byte
# received, so slow-streaming reasoning endpoints can hang forever without
# this. The call runs in a daemon thread so a hung request can never block
# process exit (ThreadPoolExecutor's atexit join would otherwise do that).
HARD_TIMEOUT = float(os.environ.get("PROVER_LLM_TIMEOUT", "180"))


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
    return os.environ.get("PROVER_MODEL", "gpt-4o")


# Rough context-window estimates per model family. Used by context_window.py to
# compute the automatic compaction budget (tau parity). Env override
# PROVER_CONTEXT_WINDOW short-circuits this lookup.
_DEFAULT_CONTEXT_WINDOW_TOKENS = {
    "gpt-4o": 128_000,
    "gpt-4-turbo": 128_000,
    "gpt-4": 8_192,
    "gpt-3.5-turbo": 16_384,
}
DEFAULT_CONTEXT_WINDOW_TOKENS = 128_000
DEFAULT_COMPACTION_RESERVE_TOKENS = 16_384


def context_window_tokens(model_name: str | None = None) -> int:
    """Return the best-known context window for the active/default model."""
    override = os.environ.get("PROVER_CONTEXT_WINDOW")
    if override and override.isdigit():
        return int(override)
    name = model_name or model()
    for prefix, window in _DEFAULT_CONTEXT_WINDOW_TOKENS.items():
        if name == prefix or name.startswith(prefix):
            return window
    return DEFAULT_CONTEXT_WINDOW_TOKENS


@dataclass
class LLMResponse:
    content: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


def _call(system: str, messages: list[dict], temperature: float, model_name: str | None = None) -> LLMResponse:
    from .thinking import reasoning_effort_for_level, thinking_level_from_env

    kwargs: dict = {
        "model": model_name or model(),
        "messages": [{"role": "system", "content": system}, *messages],
        "temperature": temperature,
        "max_tokens": 16384,
    }
    level = thinking_level_from_env()
    if level == "off" and os.environ.get("OPENAI_BASE_URL"):
        # Thinking off (the prover default, agent/thinking.py): vLLM/HF
        # endpoints serving Qwen3+ put output in a `reasoning` field and
        # burn minutes when thinking is on without the chat-template
        # switch. Proofs are repaired by the compile loop, so fast
        # non-thinking mode wins.
        kwargs["extra_body"] = {"chat_template_kwargs": {"enable_thinking": False}}
    elif level != "off":
        # Explicit thinking level (PROVER_THINKING): surface it as an
        # OpenAI-compatible reasoning effort (tau thinking.py → provider).
        kwargs["reasoning_effort"] = reasoning_effort_for_level(level)
    resp = client().chat.completions.create(**kwargs)
    usage = resp.usage
    content = resp.choices[0].message.content or ""
    if not content:
        content = getattr(resp.choices[0].message, "reasoning", None) or ""
    return LLMResponse(
        content=content,
        prompt_tokens=usage.prompt_tokens if usage else 0,
        completion_tokens=usage.completion_tokens if usage else 0,
        total_tokens=usage.total_tokens if usage else 0,
    )


class _CallResult:
    def __init__(self) -> None:
        self.response: LLMResponse | None = None
        self.error: str | None = None


def chat(
    system: str,
    messages: list[dict],
    temperature: float = 0.2,
    retries: int = 4,
    model_name: str | None = None,
) -> LLMResponse:
    """One LLM turn with a hard wall-clock cap and 429 backoff.
    Returns LLMResponse with content and token usage."""
    backoff = 5.0

    def run(result: _CallResult) -> None:
        try:
            result.response = _call(system, messages, temperature, model_name)
        except BaseException as e:  # noqa: BLE001 — report any failure as an error response
            result.error = str(e)

    for attempt in range(retries + 1):
        result = _CallResult()
        worker = threading.Thread(target=run, args=(result,), daemon=True)
        worker.start()
        worker.join(timeout=HARD_TIMEOUT)
        if worker.is_alive():
            return LLMResponse(content=f"[LLM error: hard timeout after {HARD_TIMEOUT:.0f}s]")
        if result.error:
            msg = result.error
            is_rate = "429" in msg or "rate limit" in msg.lower()
            if is_rate and attempt < retries:
                time.sleep(backoff)
                backoff = min(backoff * 2, 60.0)
                continue
            return LLMResponse(content=f"[LLM error: {msg}]")
        return result.response  # type: ignore[return-value]
    return LLMResponse(content="[LLM error: retries exhausted]")


def extract_lean_code(text: str) -> str:
    """Pull the first ```lean block out of a model reply, or return as-is."""
    import re

    m = re.search(r"```(?:lean)?\s*\n(.*?)```", text, re.DOTALL)
    return m.group(1).strip() if m else text.strip()


# Rough cost estimates per 1M tokens (USD). Update as pricing changes.
# Covers common OpenAI-compatible endpoints. Free tiers = $0.
_COST_PER_1M = {
    "gpt-4o": (5.00, 15.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4-turbo": (10.00, 30.00),
    "gpt-3.5-turbo": (0.50, 1.50),
    "qwen/qwen3-8b": (0.0, 0.0),
    "qwen/qwen3-8b-max-free": (0.0, 0.0),
    "qwen/qwen3-235b": (0.0, 0.0),
    "qwen/qwen3-max-free": (0.0, 0.0),
    "Qwen/Qwen3-8B": (0.0, 0.0),
    "Qwen/Qwen3-27B": (0.0, 0.0),
    "Qwen/Qwen3-235B": (0.0, 0.0),
}

def estimate_cost(prompt_tokens: int, completion_tokens: int, model_name: str | None = None) -> float:
    """Estimate cost in USD for the given token counts."""
    model_name = model_name or model()
    # Try exact match first, then prefix match for versioned names
    for key, (in_cost, out_cost) in _COST_PER_1M.items():
        if model_name == key or model_name.startswith(key.rstrip('-*')):
            return (prompt_tokens * in_cost + completion_tokens * out_cost) / 1_000_000
    # Unknown model: assume free (conservative for budgeting)
    return 0.0
