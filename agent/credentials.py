"""Credential storage — Tau credentials.py port (Tau 37a9e43 src/tau_coding/credentials.py), lean-adapted.

``FileCredentialStore`` persists OAuth credentials (per-provider
``OAuthCredential``) in ``~/.prover/credentials`` (JSON, chmod 0600).
Env-var fallback lets CI/headless flows inject tokens without a store.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class OAuthCredential:
    """One stored credential for a provider (tau OAuthCredential)."""

    provider: str
    access_token: str
    refresh_token: str | None = None
    expires_at: float | None = None
    issued_at: float = 0.0
    extras: dict | None = None

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.time() >= self.expires_at - 30.0

    def to_dict(self) -> dict:
        data = {
            "provider": self.provider,
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at,
            "issued_at": self.issued_at,
        }
        if self.extras:
            data["extras"] = self.extras
        return data

    @classmethod
    def from_dict(cls, data: dict) -> OAuthCredential:
        return cls(
            provider=str(data.get("provider") or ""),
            access_token=str(data.get("access_token") or ""),
            refresh_token=data.get("refresh_token"),
            expires_at=data.get("expires_at"),
            issued_at=float(data.get("issued_at") or time.time()),
            extras=data.get("extras") if isinstance(data.get("extras"), dict) else None,
        )


def credentials_path() -> Path:
    """The credential store file (``~/.prover/credentials``)."""
    from .paths import ProverPaths

    override = os.environ.get("PROVER_CREDENTIALS_PATH")
    if override:
        return Path(override)
    return ProverPaths().config_dir / "credentials"


class FileCredentialStore:
    """JSON-file credential store (tau FileCredentialStore)."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or credentials_path()

    def _load_all(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}

    def _write_all(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(data, indent=2) + "\n"
        # Write to a temp file in the same dir, chmod 0600 before the secret
        # content is placed, then atomically rename — readers never observe a
        # partial/absent file, and the world never sees a world-readable window.
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".creds-")
        try:
            os.chmod(tmp, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(payload)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def get(self, provider: str) -> OAuthCredential | None:
        if not provider:
            return None
        # Env-var override for CI/headless.
        env_var = f"{provider.upper().replace('-', '_')}_OAUTH_TOKEN"
        env_token = os.environ.get(env_var)
        if env_token:
            return OAuthCredential(provider=provider, access_token=env_token)
        stored = self._load_all().get(provider)
        if isinstance(stored, dict):
            return OAuthCredential.from_dict(stored)
        return None

    def set(self, credential: OAuthCredential) -> None:
        data = self._load_all()
        data[credential.provider] = credential.to_dict()
        self._write_all(data)

    def delete(self, provider: str) -> bool:
        data = self._load_all()
        if provider in data:
            del data[provider]
            self._write_all(data)
            return True
        return False

    def providers(self) -> list[str]:
        return sorted(self._load_all().keys())
