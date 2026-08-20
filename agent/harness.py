from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AgentHarness:
    model: str = "gpt-4o"
    system: str = ""

    async def prompt(self, text: str):
        from .loop import prove

        r = prove(text)
        yield {"type": "result", "proved": r.proved, "proof": r.proof}
