from __future__ import annotations

import hashlib


def portable_tool_call_id(raw: str) -> str:
    return "tc_" + hashlib.sha256(raw.encode()).hexdigest()[:16]
