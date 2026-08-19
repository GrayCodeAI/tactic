#!/usr/bin/env bash
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
    return {"text": "

".join(m["role"] + ": " + m["content"] for m in r["messages"])}
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
