"""Anthropic device-code OAuth — Tau oauth_anthropic.py port (Tau 37a9e43 src/tau_coding/oauth_anthropic.py), lean-adapted.

Anthropic's Claude Desktop OAuth is an OAuth 2.0 device-authorization flow.
This port requests a device code from Anthropic's token endpoint, displays
the user-code prompt, and polls via ``poll_oauth_device_code``.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from collections.abc import Callable
from urllib.request import Request, urlopen

from ..credentials import FileCredentialStore, OAuthCredential
from .device import DeviceFlowError, parse_device_code_response, poll_oauth_device_code
from .types import OAuthPrompt

ANTHROPIC_DEVICE_CODE_URL = "https://console.anthropic.com/oauth/device/code"
ANTHROPIC_TOKEN_URL = "https://console.anthropic.com/oauth/token"
ANTHROPIC_CLIENT_ID = "claude.desktop"
ANTHROPIC_SCOPE = "user:inference user:profile"

import time


def _post_json(url: str, fields: dict[str, str]) -> dict | None:
    data = urllib.parse.urlencode(fields).encode()
    req = Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("Accept", "application/json")
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except Exception:  # noqa: BLE001
        return None


async def login_anthropic(
    prompt_callback: Callable[[OAuthPrompt], object] | None = None,
    *,
    credential_store: FileCredentialStore | None = None,
    client_id: str = ANTHROPIC_CLIENT_ID,
    should_stop: Callable[[], bool] | None = None,
) -> OAuthCredential | None:
    """Run the Anthropic device-code login; persist on success."""
    auth = _post_json(
        ANTHROPIC_DEVICE_CODE_URL,
        {"client_id": client_id, "scope": ANTHROPIC_SCOPE},
    )
    if auth is None or not auth.get("device_code"):
        return None
    device = parse_device_code_response(auth)
    if prompt_callback is not None:
        prompt_callback(
            OAuthPrompt(
                kind="url",
                text=f"Visit {device.verification_uri} and enter code {device.user_code}",
                url=device.verification_uri,
            )
        )

    async def fetch_token(device_code: str) -> dict | None:
        return _post_json(
            ANTHROPIC_TOKEN_URL,
            {
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "device_code": device_code,
                "client_id": client_id,
            },
        )

    try:
        token = await poll_oauth_device_code(device, fetch_token, should_stop=should_stop)
    except DeviceFlowError:
        return None
    if token is None or not token.get("access_token"):
        return None
    credential = OAuthCredential(
        provider="anthropic",
        access_token=str(token["access_token"]),
        refresh_token=token.get("refresh_token"),
        expires_at=(time.time() + float(token["expires_in"])) if token.get("expires_in") else None,
    )
    store = credential_store or FileCredentialStore()
    store.set(credential)
    return credential


async def refresh_anthropic(refresh_token_value: str, client_id: str = ANTHROPIC_CLIENT_ID) -> dict | None:
    return _post_json(
        ANTHROPIC_TOKEN_URL,
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token_value,
            "client_id": client_id,
        },
    )
