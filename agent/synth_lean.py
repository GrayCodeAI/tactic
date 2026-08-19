"""Lean-native proof corpus generator (`prover synth-lean`).

Reads a baseline report (`benchmark/lean_baseline.json`) and writes a JSONL
corpus of `{"statement", "tactic", "id", "difficulty"}` entries for exactly
the statements Lean itself proved — the "expert" half of expert iteration
with zero model cost. Python only aggregates; every check is Lean.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load_report(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def corpus_lines(report: dict) -> list[dict]:
    tactic = report.get("tactic", "prover_finish")
    return [
        {
            "id": s.get("id", f"p{i}"),
            "difficulty": s.get("difficulty", "unknown"),
            "statement": s["statement"],
            "tactic": tactic,
        }
        for i, s in enumerate(report.get("solved_ids", []), 1)
    ]


def write_corpus(report: dict, out: Path) -> int:
    entries = corpus_lines(report)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    return len(entries)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--report", default="benchmark/lean_baseline.json",
                    help="baseline JSON report (default benchmark/lean_baseline.json)")
    ap.add_argument("--out", default="corpus/lean_proved.jsonl",
                    help="output JSONL path")
    args = ap.parse_args(argv)

    report = load_report(Path(args.report))
    n = write_corpus(report, Path(args.out))
    print(f"corpus: {n} Lean-proved entries from report "
          f"'{args.report}' (tactic={report.get('tactic')})")
    print(f"written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
