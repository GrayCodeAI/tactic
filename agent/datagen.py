"""SFT/RL data generation from Lean-verified corpus (agent/datagen).

Every assumption is explicit: this module produces the *expert* half of expert
iteration and of any later fine-tune — (statement, tactic) pairs where the
tactic is exactly what Lean itself accepted. No model involvement, no
internet, no secrets.

Data sources (merged, deduped by id):
- `corpus/lean_proved.jsonl` — 103+ entries from the baseline + synthesized
  templates + auto-growth during proving.
- JSON reports under `benchmark/` (`--report PATH` may be repeated).

Output: `benchmark/train_sft.jsonl` with one JSON per line:
```
{"id", "source", "statement", "tactic", "fidelity"}
```
`fidelity` is the "replay category": `native` for hammer/search files (the
tactic is the chain itself — up to verifier), `templated` for mathlib-style
templates, `auto` for loop-grown entries. The `tactic` column is always
exactly the one verified during corpus construction — we never fabricate or
guess a proof.

Intended use (documented, not enforced): keypoints for supervised
fine-tune on any OpenAI-compatible chat model; instructions say "prove
the Lean theorem below; reply with only the tactic body".
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

FIDELITY_SYSTEM = (
    "You are a Lean 4 proof assistant. You are given a theorem statement in "
    "Lean 4 in mathlib. Write only the tactic body that proves it. No prose, "
    "no markdown fences."
)


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _entry_from_report(path: Path, fid: str) -> list[dict]:
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    tactic = report.get("tactic", "prover_finish")
    if tactic == "prover_search":
        tactic = f"prover_search {report.get('search_depth', 3)}"
        budget = report.get("search_budget") or 1000
        if budget != 1000:
            # Budget rides as a file-level option, not a tactic arg.
            tactic = f"set_option prover_search.budget {budget}\n{tactic}"
    return [
        {"id": s.get("id", f"{path.stem}_{i}"),
         "source": path.name,
         "statement": s["statement"].split(":=")[0].strip(),
         "tactic": tactic,
         "fidelity": fid}
        for i, s in enumerate(report.get("solved_ids", []))
    ]


def gather(corpus_path: Path, reports: list[Path]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []

    def add(entry: dict) -> None:
        if entry["statement"] and entry["id"] not in seen:
            seen.add(entry["id"])
            out.append(entry)

    for e in _read_jsonl(corpus_path):
        stmt = str(e.get("statement", ""))
        tactic = str(e.get("tactic", ""))
        diff = str(e.get("difficulty", ""))
        add({
            "id": str(e.get("id", "?")),
            "source": "corpus",
            "statement": stmt.split(":=")[0].strip() if stmt else "",
            "tactic": tactic,
            "fidelity": "auto" if diff == "auto" else "templated",
        })
    for p in reports:
        for e in _entry_from_report(p, "native"):
            add(e)
    return out


def write_sft(entries: list[dict], out: Path) -> int:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for e in entries:
            json.dump(
                {
                    "id": e["id"],
                    "system": FIDELITY_SYSTEM,
                    "instruction": e["statement"],
                    "output": f"```lean\n  {e['tactic']}\n```",
                    "source": e["source"],
                    "fidelity": e["fidelity"],
                }, f, ensure_ascii=False)
            f.write("\n")
    return len(entries)


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus", default="corpus/lean_proved.jsonl")
    ap.add_argument("--report", action="append", default=[],
                    help="JSON report (repeatable); default: all committed "
                         "baseline reports under benchmark/")
    ap.add_argument("--out", default="benchmark/train_sft.jsonl")
    args = ap.parse_args(argv)

    from .loop import LEAN_DIR

    corpus = LEAN_DIR.parent / args.corpus
    reports = [Path(r) for r in args.report]
    if not reports:
        default_dir = Path("benchmark")
        if default_dir.exists():
            reports = sorted(
                p for p in default_dir.glob("lean_baseline*.json")
                if p.stem != "lean_baseline_search4k"  # running, incomplete
            )
    entries = gather(corpus, reports)
    if not entries:
        print("no entries gathered (missing corpus + reports?)", file=sys.stderr)
        return 1
    n = write_sft(entries, Path(args.out))
    fid = {e["fidelity"]: 0 for e in entries}
    for e in entries:
        fid[e["fidelity"]] += 1
    print(f"datagen: {n} entries → {args.out}  "
          + ", ".join(f"{k}={v}" for k, v in sorted(fid.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
