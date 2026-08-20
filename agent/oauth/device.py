"""RFC 8628 device-code polling — Tau oauth_device.py port.

``poll_oauth_device_code`` drives a device-flow token poll loop: takes a
device-code response dict and a ``fetch()`` awaitable that performs one token
poll, sleeping ``interval`` seconds until success, expiry, slow_down, or
user abort via an optional should-stop callback.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any


class DeviceFlowError(RuntimeError):
    def __init__(self, error: str, description: str | None = None) -> None:
        super().__init__(error)
        self.error = error
        self.description = description


@dataclass(frozen=True, slots=True)
class DeviceCodeResponse:
    device_code: str
    user_code: str
    verification_uri: str
    verification_uri_complete: str | None = None
    expires_in: int = 600
    interval: int = 5


def parse_device_code_response(data: dict[str, Any]) -> DeviceCodeResponse:
    return DeviceCodeResponse(
        device_code=str(data.get("device_code") or ""),
        user_code=str(data.get("user_code") or ""),
        verification_uri=str(data.get("verification_uri") or data.get("verification_url") or ""),
        verification_uri_complete=data.get("verification_uri_complete"),
        expires_in=int(data.get("expires_in") or 600),
        interval=int(data.get("interval") or 5),
    )


async def poll_oauth_device_code(
    response: DeviceCodeResponse,
    fetch_token: Callable[[str], Awaitable[dict[str, Any] | None]],
    *,
    should_stop: Callable[[], bool] | None = None,
    on_slow_down: Callable[[int], None] | None = None,
) -> dict[str, Any] | None:
    """Poll ``fetch_token`` until a token response or terminal condition.

    Returns the token dict, or None on expiry/abort. Raises DeviceFlowError
    for ``access_denied``/other non-transient errors. ``slow_down`` bumps the
    interval (RFC 8628 §3.5) through the optional callback.
    """
    import time

    deadline = time.monotonic() + response.expires_in
    interval = max(1, response.interval)
    while time.monotonic() < deadline:
        if should_stop is not None and should_stop():
            return None
        result = await fetch_token(response.device_code)
        if result is None:
            await asyncio.sleep(interval)
            continue
        error = result.get("error")
        if error is None and result.get("access_token"):
            return result
        if error == "authorization_pending":
            await asyncio.sleep(interval)
        elif error == "slow_down":
            interval += 5
            if on_slow_down is not None:
                on_slow_down(interval)
            await asyncio.sleep(interval)
        elif error == "expired_token":
            return None
        elif error == "access_denied":
            raise DeviceFlowError("access_denied", str(result.get("error_description") or "user denied access"))
        else:
            raise DeviceFlowError(str(error or "unknown"), str(result.get("error_description") or None))
    return None
