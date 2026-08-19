"""Unit tests for the LSP runTactic primitive (agent/lsp.py).

The real `lean --server` process is not spun up here: we drive the RPC
framing and goal formatting against a mocked `_request` (and a trivial fake
process for the send/read plumbing).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agent import lsp


@pytest.fixture
def client(tmp_path: Path, monkeypatch) -> lsp.LeanLSP:
    f = tmp_path / "T.lean"
    f.write_text("theorem t (n : ℕ) : n = n := by\n  sorry\n", encoding="utf-8")
    c = lsp.LeanLSP(tmp_path, f)
    # stub the process plumbing so no subprocess is spawned
    c._opened = True
    c._send = lambda _obj: None  # type: ignore[method-assign]
    c._ensure_started = lambda: True  # type: ignore[method-assign]
    monkeypatch.setattr(lsp, "LSP_TIMEOUT", 5)
    return c


def test_run_tactic_frames_rpc_call(client: lsp.LeanLSP, monkeypatch) -> None:
    calls: list[tuple[str, dict]] = []

    def fake_request(method: str, params: dict, timeout: float | None = None) -> dict | None:
        calls.append((method, params))
        if method == "$/lean/rpc/connect":
            return {"result": {"sessionId": "sess-1"}}
        if method == "$/lean/rpc/call":
            assert params["method"] == "Lean.Widget.runTactic"
            inner = params["params"]
            assert inner["tactic"] == "rfl"
            assert inner["position"] == {"line": 2, "character": 4}
            return {"result": {"goals": []}}
        return {"error": "unexpected"}

    monkeypatch.setattr(client, "_request", fake_request)
    client.run_tactic("theorem t (n : ℕ) : n = n := by\n  sorry\n", "rfl",
                      line=2, character=4)
    methods = [m for m, _ in calls]
    assert methods == ["$/lean/rpc/connect", "$/lean/rpc/call"]


def test_run_tactic_formats_result_goals(client: lsp.LeanLSP, monkeypatch) -> None:
    def fake_request(method: str, params: dict, timeout: float | None = None) -> dict | None:
        if method == "$/lean/rpc/connect":
            return {"result": {"sessionId": "sess-1"}}
        if method == "$/lean/rpc/call":
            return {"result": {"goals": [{
                "goalPrefix": "⊢",
                "type": {"text": " n + 0 = n"},
                "hyps": [{"names": ["n"], "type": {"text": "ℕ"}}],
            }]}}
        return {"error": "unexpected"}

    monkeypatch.setattr(client, "_request", fake_request)
    out = client.run_tactic("theorem t (n : ℕ) : n + 0 = n := by\n  sorry\n", "omega")
    assert out == "n : ℕ\n⊢ n + 0 = n"


def test_run_tactic_default_position_end_of_file(client: lsp.LeanLSP, monkeypatch) -> None:
    seen: list[dict] = []

    def fake_request(method: str, params: dict, timeout: float | None = None) -> dict | None:
        if method == "$/lean/rpc/connect":
            return {"result": {"sessionId": "sess-1"}}
        if method == "$/lean/rpc/call":
            seen.append(params["params"])
            return {"result": {"goals": []}}
        return {"error": "unexpected"}

    monkeypatch.setattr(client, "_request", fake_request)
    client.run_tactic("theorem t : True := by\n  sorry\n", "trivial")
    # end of the last non-empty line ("  sorry", line 1)
    assert seen[0]["position"] == {"line": 1, "character": 7}


def test_run_tactic_returns_none_on_rpc_error(client: lsp.LeanLSP, monkeypatch) -> None:
    def fake_request(method: str, params: dict, timeout: float | None = None) -> dict | None:
        return {"error": {"code": -32601, "message": "unknown method"}}

    monkeypatch.setattr(client, "_request", fake_request)
    assert client.run_tactic("theorem t : True := by sorry", "trivial") is None


def test_run_tactic_returns_none_on_null_result(client: lsp.LeanLSP, monkeypatch) -> None:
    def fake_request(method: str, params: dict, timeout: float | None = None) -> dict | None:
        if method == "$/lean/rpc/connect":
            return {"result": {"sessionId": "sess-1"}}
        return {"result": None}

    monkeypatch.setattr(client, "_request", fake_request)
    assert client.run_tactic("theorem t : True := by sorry", "trivial") is None
