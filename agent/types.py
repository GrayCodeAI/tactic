from __future__ import annotations

from typing import Any, TypeAlias

JSONPrimitive: TypeAlias = str | int | float | bool | None
JSONValue: TypeAlias = Any
JSONObject: TypeAlias = dict[str, Any]
