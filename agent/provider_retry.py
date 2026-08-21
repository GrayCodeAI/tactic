from __future__ import annotations

import random
import time

RETRY_POLL_SECONDS = 0.05
RETRY_BASE_DELAY_SECONDS = 0.25


def retry_delay_seconds(attempt: int, *, max_delay_seconds: float) -> float:
    if max_delay_seconds <= 0:
        return 0.0
    base_delay = min(RETRY_BASE_DELAY_SECONDS, max_delay_seconds)
    delay = float(min(max_delay_seconds, base_delay * (2**attempt)))
    # Full jitter avoids thundering-herd alignment on shared endpoints while
    # keeping the worst case bounded by the exponential delay.
    return random.uniform(0.0, delay)


def provider_retry_message(*, attempt: int, max_retries: int, delay_seconds: float, reason: str) -> str:
    next_attempt = attempt + 2
    max_attempts = max_retries + 1
    delay_suffix = f" in {delay_seconds:g}s" if delay_seconds else ""
    return f"Retrying provider request {next_attempt}/{max_attempts} after {reason}{delay_suffix}."


def wait_for_retry(delay_seconds: float) -> bool:
    if delay_seconds <= 0:
        return True
    time.sleep(delay_seconds)
    return True
