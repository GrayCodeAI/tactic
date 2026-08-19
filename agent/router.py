"""Per-difficulty model/temperature/step routing for proof attempts.

Env table (all optional; TIER = the problem difficulty uppercased):

    PROVER_MODEL_<TIER>   model name for that tier (else PROVER_MODEL / default)
    PROVER_TEMP_<TIER>    sampling temperature for that tier
    PROVER_STEPS_<TIER>   max repair steps for that tier

``select()`` never raises and never guesses: values absent from the
environment fall back to the caller's defaults. Unknown difficulties simply
get the generic ``PROVER_MODEL``.
"""

from __future__ import annotations

import os

from . import llm


def _float_env(name: str) -> float | None:
    raw = os.getenv(name)
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _int_env(name: str) -> int | None:
    raw = os.getenv(name)
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def select(
    difficulty: str | None,
    *,
    model: str | None = None,
    temperature: float | None = None,
    max_steps: int | None = None,
) -> dict:
    """Resolve the routing config for a difficulty.

    Always returns a dict with ``model`` set. ``temperature`` / ``max_steps``
    are only present when an env override exists (callers fall back to their
    own defaults otherwise).
    """
    tier = difficulty.upper() if difficulty else ""
    cfg: dict = {}
    model_name = (
        os.getenv(f"PROVER_MODEL_{tier}")
        or model
        or llm.model()
    )
    cfg["model"] = model_name
    if tier:
        t = _float_env(f"PROVER_TEMP_{tier}")
        if t is not None:
            cfg["temperature"] = t
        s = _int_env(f"PROVER_STEPS_{tier}")
        if s is not None:
            cfg["max_steps"] = s
    return cfg
