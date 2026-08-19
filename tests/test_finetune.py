"""Unit tests for LoRA data prep + fidelity (agent/finetune.py)."""

from __future__ import annotations

import json
from pathlib import Path

from agent import finetune


def _write_sft(tmp_path: Path) -> Path:
    entries = [
        {"id": "a", "system": "sys", "instruction": "theorem a : True",
         "output": "```lean\n  trivial\n```", "source": "corpus",
         "fidelity": "templated"},
        {"id": "b", "system": "sys", "instruction": "theorem b : True",
         "output": "```lean\n  sorry\n```", "source": "corpus",
         "fidelity": "auto"},
    ]
    p = tmp_path / "train_sft.jsonl"
    p.write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in entries),
                 encoding="utf-8")
    return p


def test_prepare_filters_sorry_and_writes_chat(tmp_path: Path) -> None:
    sft = _write_sft(tmp_path)
    chat = tmp_path / "train_chat.jsonl"
    launcher = tmp_path / "finetune_lora.sh"
    assert finetune.prepare(sft, chat, launcher) == 0
    rec = json.loads(chat.read_text(encoding="utf-8"))
    assert rec["id"] == "a"
    assert rec["messages"][2]["role"] == "assistant"
    assert launcher.exists() and "torch.cuda.is_available" in launcher.read_text()


def test_extract_tactic_strips_fence_and_header() -> None:
    body = finetune._extract_tactic("```lean\ntheorem x : True := by\n  trivial\n```")
    assert "theorem" not in body and body.strip() == "trivial"
    body = finetune._extract_tactic("set_option maxHeartbeats 0\n  omega")
    assert "set_option maxHeartbeats 0" in body and "omega" in body


def test_fidelity_keeps_only_lean_certified(tmp_path: Path, monkeypatch) -> None:
    chat = tmp_path / "train_chat.jsonl"
    entries = [
        {"id": f"p{i}", "messages": [
            {"role": "system", "content": "s"},
            {"role": "user", "content": f"theorem p{i} : True"},
            {"role": "assistant", "content": f"```lean\n  trivial{i // 2}\n```"},
        ]}
        for i in range(4)
    ]
    chat.write_text("\n".join(json.dumps(e) for e in entries), encoding="utf-8")

    def fake_check(f, lean_dir, timeout=120):
        idx = int(f.stem.split("_")[1])  # fidelity_0001 -> 1
        ok = idx % 2 == 1  # certify entries 1,3 (p0, p2)
        return ok, ("" if ok else "stuck proof")

    monkeypatch.setattr("agent.lean.check_file", fake_check)
    report = tmp_path / "report.json"
    out = tmp_path / "chat_fidelity.jsonl"
    assert finetune.fidelity(chat, report, out, timeout=5) == 0
    rep = json.loads(report.read_text(encoding="utf-8"))
    assert rep["total"] == 4 and rep["certified"] == 2
    surviving = {json.loads(l)["id"] for l in out.read_text().splitlines()}
    assert surviving == {"p0", "p2"}
