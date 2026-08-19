"""Synthetic proof data generation + expert iteration corpus.

``generate()`` runs the repair loop over a set of seed statements and emits
two JSONL files:

* ``<out>``          — every attempt (proved or not): statement, proof, steps,
                       tokens, seconds.
* ``<out>`` with ``_train`` before the suffix — ONLY the PROVEN examples,
                       the (statement, proof) pairs usable for SFT.

This is the honest half of "expert iteration": we produce the corpus, we do
not claim to fine-tune (that needs a GPU and is out of scope here).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from .loop import prove_best_of


def generate(
    seeds: list[str],
    out_path: str,
    max_steps: int = 15,
    model_name: str | None = None,
    skip_hammers: bool = False,
) -> dict:
    """Prove each seed; write <out> (all) and <train> (proven only)."""
    rows = []
    for i, stmt in enumerate(seeds, 1):
        r = prove_best_of(stmt, n_attempts=1, max_steps=max_steps, verbose=False,
                          problem_id=f"synth_{i}", goal_feedback=False,
                          record_session=False, model_name=model_name,
                          skip_hammers=skip_hammers)
        rows.append({
            "statement": stmt,
            "proof": r.proof,
            "proved": r.proved,
            "steps": r.steps,
            "tokens": r.total_tokens,
            "seconds": round(r.seconds, 2),
            "attempts": len(r.attempts),
        })

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    _write_jsonl(out, rows)

    train = [r for r in rows if r["proved"]]
    train_path = out.with_name(out.stem + "_train" + out.suffix)
    _write_jsonl(train_path, train)

    return {
        "total": len(rows),
        "proved": len(train),
        "exhausted": len(rows) - len(train),
        "all": str(out),
        "train": str(train_path),
    }


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="synth.jsonl", help="output JSONL (train file derived)")
    ap.add_argument("--count", type=int, default=20, help="number of seed statements")
    ap.add_argument("--seeds", default=None, help="file with one statement per line (overrides --count)")
    ap.add_argument("--problems", default="benchmark/problems.json",
                    help="JSON problems file to seed from (when --seeds absent)")
    ap.add_argument("--max-steps", type=int, default=15)
    ap.add_argument("--model", default=None, help="model name (default: PROVER_MODEL)")
    ap.add_argument("--no-hammers", action="store_true", help="skip hammer pre-pass")
    args = ap.parse_args(argv)

    if args.seeds:
        seeds = [ln.strip() for ln in Path(args.seeds).read_text(encoding="utf-8").splitlines() if ln.strip()]
    else:
        problems = json.loads(Path(args.problems).read_text(encoding="utf-8"))
        seeds = [p["statement"] for p in problems[: args.count]]
    if not seeds:
        print("no seed statements; nothing to do", file=sys.stderr)
        return 1

    print(f"proving {len(seeds)} seeds (max {args.max_steps} steps each)...")
    summary = generate(seeds, args.out, max_steps=args.max_steps,
                       model_name=args.model or None, skip_hammers=args.no_hammers)
    print(f"total={summary['total']} proved={summary['proved']} exhausted={summary['exhausted']}")
    print(f"all:   {summary['all']}")
    print(f"train: {summary['train']}")
    return 0
