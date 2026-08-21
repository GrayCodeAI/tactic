from __future__ import annotations

import random

RETRY_BASE_DELAY_SECONDS = 0.25


def retry_delay_seconds(attempt: int, *, max_delay_seconds: float) -> float:
    if max_delay_seconds <= 0:
        return 0.0
    base_delay = min(RETRY_BASE_DELAY_SECONDS, max_delay_seconds)
    delay = float(min(max_delay_seconds, base_delay * (2**attempt)))
    # Full jitter avoids thundering-herd alignment on shared endpoints while
    # keeping the worst case bounded by the exponential delay.
    return random.uniform(0.0, delay)
