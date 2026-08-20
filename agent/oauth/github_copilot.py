"""GitHub Copilot device-code OAuth — Tau oauth_github_copilot.py port (Tau 37a9e43 src/tau_coding/oauth_github_copilot.py), lean-adapted.

Copilot's OAuth flow is device-code based with a ``copilot_internal/v2/token``
exchange. This port requests a device code from GitHub, displays the user code
prompt, and polls via ``poll_oauth_device_code``.
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

GITHUB_CLIENT_ID = "2b01893e4b92f7498773"
GITHUB_SCOPE = "read:user repo user:email"
GITHUB_DEVICE_URL = "https://github.com/login/device/code"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"


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


async def login_github_copilot(
    prompt_callback: Callable[[OAuthPrompt], object] | None = None,
    *,
    credential_store: FileCredentialStore | None = None,
    client_id: str = GITHUB_CLIENT_ID,
    should_stop: Callable[[], bool] | None = None,
) -> OAuthCredential | None:
    """Run the GitHub Copilot device-code login; persist on success."""
    auth = _post_json(GITHUB_DEVICE_URL, {
        "client_id": client_id,
        "scope": GITHUB_SCOPE,
    })
    if auth is None or not auth.get("device_code"):
        return None
    device = parse_device_code_response(auth)
    if prompt_callback is not None:
        prompt_callback(OAuthPrompt(
            kind="url",
            text=f"Open {device.verification_uri} and enter {device.user_code}",
            url=device.verification_uri,
        ))

    async def fetch_token(device_code: str) -> dict | None:
        return _post_json(GITHUB_TOKEN_URL, {
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "device_code": device_code,
            "client_id": client_id,
        })

    try:
        token = await poll_oauth_device_code(device, fetch_token, should_stop=should_stop)
    except DeviceFlowError:
        return None
    if token is None or not token.get("access_token"):
        return None
    credential = OAuthCredential(
        provider="github-copilot",
        access_token=str(token["access_token"]),
        refresh_token=token.get("refresh_token"),
    )
    store = credential_store or FileCredentialStore()
    store.set(credential)
    return credential
