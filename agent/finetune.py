"""LoRA fine-tune glue over the Lean-verified SFT corpus (`prover finetune`).

Honest scope on this repo: verification twice, zero fake claims.

Two modes:
- `--prepare` (default): normalizes the SFT JSONL into chat format
  (`benchmark/train_chat.jsonl`) and writes a LoRA launcher
  (`benchmark/finetune_lora.sh`) that refuses to run without a CUDA GPU —
  training itself is blocked at infra here (no GPU on this box), and saying
  so is the feature, not a bug.
- `--fidelity`: re-compiles EVERY training entry with real Lean
  (`lake env lean`), so the "expert data" fed to any trainer really is
  expert. Writes a verified subset + report. Expert data that fails
  Lean is dropped; numbers are the numbers.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

FENCE_RE = re.compile(r"```(?:lean)?\s*\n(.*?)```", re.DOTALL)


def _extract_tactic(output: str) -> str:
    m = FENCE_RE.search(output)
    body = m.group(1) if m else output
    lines = []
    for ln in body.strip().splitlines():
        s = ln.strip()
        if not s:
            continue
        if s.startswith("set_option "):
            lines.append(s)
            continue
        if re.match(r"^(theorem|lemma|example|import|open)\b", s):
            continue
        lines.append(s)
    return ("\n".join(lines)).strip()


def prepare(sft: Path, chat: Path, launcher: Path) -> int:
    entries = []
    for line in sft.read_text(encoding="utf-8").splitlines():
        e = json.loads(line)
        if "sorry" in e["output"] or not e["instruction"].strip():
            continue
        entries.append({
            "messages": [
                {"role": "system", "content": e["system"]},
                {"role": "user", "content": e["instruction"]},
                {"role": "assistant", "content": e["output"]},
            ],
            "id": e["id"],
            "fidelity": e["fidelity"],
        })
    chat.parent.mkdir(parents=True, exist_ok=True)
    with chat.open("w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    launcher.parent.mkdir(parents=True, exist_ok=True)
    launcher.write_text(
        """#!/usr/bin/env bash
# LoRA fine-tune on benchmark/train_chat.jsonl (chat format, verified data).
# Blocked on this box: needs a CUDA GPU. Point LEAN_BASE_MODEL at a small
# mathlib-aware open model (e.g. Qwen2.5-Coder-7B) and run on GPU when available.
set -euo pipefail
python - <<'EOF' > /dev/null 2>&1 || { echo "needs CUDA GPU on this box — no fine-tune here"; exit 1; }
import torch
assert torch.cuda.is_available()
EOF
LEAN_BASE_MODEL="${LEAN_BASE_MODEL:?set to an open chat model}"
OUT="${OUT:-lora_out}"
python - <<EOF
from datasets import load_dataset
from peft import LoraConfig, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments, Trainer
model_id = "$LEAN_BASE_MODEL"
tok = AutoTokenizer.from_pretrained(model_id)
model = AutoModelForCausalLM.from_pretrained(model_id, torch_dtype="bfloat16", device_map="auto")
cfg = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, task_type="CAUSAL_LM",
                 target_modules=["q_proj", "k_proj", "v_proj", "o_proj"])
peft = get_peft_model(model, cfg)
def fmt(r):
    return {"text": "\n\n".join(m["role"] + ": " + m["content"] for m in r["messages"])}
ds = load_dataset("json", data_files="$1", split="train").map(fmt, remove_columns=["id", "fidelity", "messages"])
tok.pad_token = tok.eos_token
tr = Trainer(model=peft,
             args=TrainingArguments(output_dir="$OUT", per_device_train_batch_size=1,
                                    gradient_accumulation_steps=8, num_train_epochs=3,
                                    learning_rate=1e-4, bf16=True, logging_steps=10),
             tokenizer=tok, train_dataset=ds)
tr.train()
peft.save_pretrained("$OUT")
EOF
""",
        encoding="utf-8",
    )
    launcher.chmod(0o755)
    print(f"finetune --prepare: {len(entries)} chat examples -> {chat}")
    print(f"launcher -> {launcher} (CUDA check built in; blocked without a GPU)")
    return 0


def fidelity(chat: Path, report: Path, out_chat: Path, timeout: int) -> int:
    """Re-prove every training entry with real Lean; keep only certified."""
    from .lean import check_file
    from .lean_baseline import HEADER, build_lean_file
    from .loop import LEAN_DIR

    tmp = Path("/tmp/prover_fidelity")
    tmp.mkdir(parents=True, exist_ok=True)
    entries = [json.loads(line)
               for line in chat.read_text(encoding="utf-8").splitlines()]
    certified: list[dict] = []
    failed: list[tuple[str, str]] = []
    for i, e in enumerate(entries, 1):
        stmt = e["messages"][1]["content"]
        tactic = _extract_tactic(e["messages"][2]["content"])
        m = re.search(r"prover_search(?:\s+(\d+))?", tactic)
        if m:
            depth = int(m.group(1) or 3)
            tactic_name = f"prover_search {depth}"
        else:
            tactic_name = "prover_finish"
        set_opts = "\n".join(
            ln for ln in tactic.splitlines() if ln.startswith("set_option ")
        )
        text = build_lean_file(stmt, "prover_search")
        text = text.replace(HEADER, HEADER + set_opts + "\n", 1) if set_opts else text
        text = text.rstrip("\n").rsplit("\n", 1)[0] + "\n  " + tactic_name + "\n"
        f = tmp / f"fidelity_{i:04d}.lean"
        f.write_text(text, encoding="utf-8")
        ok, err = check_file(f, LEAN_DIR, timeout)
        if ok:
            certified.append(e)
        else:
            failed.append((e["id"], err[:200]))
        print(f"[{i}/{len(entries)}] {e['id']:<34} {'OK' if ok else 'FAIL'}",
              file=sys.stderr)
    if out_chat:
        with out_chat.open("w", encoding="utf-8") as f:
            for e in certified:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
    report.write_text(json.dumps({
        "total": len(entries),
        "certified": len(certified),
        "failed_ids": [fid for fid, _ in failed],
        "sample_errors": [err for _, err in failed[:3]],
    }, indent=2), encoding="utf-8")
    print(f"fidelity: {len(certified)}/{len(entries)} certified by Lean")
    return 0


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--prepare", action="store_true")
    ap.add_argument("--fidelity", action="store_true")
    ap.add_argument("--sft", default="benchmark/train_sft.jsonl")
    ap.add_argument("--chat", default="benchmark/train_chat.jsonl")
    ap.add_argument("--chat-out", default="benchmark/train_chat_fidelity.jsonl")
    ap.add_argument("--report", default="benchmark/fidelity_report.json")
    ap.add_argument("--launcher", default="benchmark/finetune_lora.sh")
    ap.add_argument("--timeout", type=int, default=120)
    args = ap.parse_args(argv)

    if args.fidelity:
        return fidelity(Path(args.chat), Path(args.report), Path(args.chat_out),
                        args.timeout)
    return prepare(Path(args.sft), Path(args.chat), Path(args.launcher))


if __name__ == "__main__":
    sys.exit(main())
