from __future__ import annotations

import json
from pathlib import Path


def load_catalog(path: Path | None = None) -> dict:
    from .paths import ProverPaths

    p = path or ProverPaths().config_dir / "catalog.json"
    if not p.exists():
        return {"models": [], "providers": []}
    try:
        return json.loads(p.read_text())
    except Exception:  # noqa: BLE001
        return {"models": [], "providers": []}
