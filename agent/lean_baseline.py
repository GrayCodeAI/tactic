"""Lean-native no-LLM baseline runner (`prover lean-baseline`).

For every problem in a benchmark JSON file we run ONE `lake env lean` per
problem: `import ProverSupport` + the theorem statement + the hammer chain
(`prover_finish`). No LLM, no repair loop, no search — this is the honest
"what does Lean itself solve" floor that the agent must beat.

Output is a per-tier table plus solved/unsolved lists, written to a JSON
report (default `benchmark/lean_baseline.json`). Everything here is Python
only as a driver; every check is Lean.
"""

from __future__ import annotations

import json
import re
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from .lean import check_file

HEADER = "import Mathlib\nimport ProverSupport\n\nopen BigOperators Nat Finset\n\n"
SEARCH_OPTIONS = "set_option maxHeartbeats 0\n\n"


def _signature(statement: str) -> str:
    s = statement.strip()
    m = re.search(r":=\s*by\b", s)
    if m:
        return s[: m.end()]
    return s + " := by"


def build_lean_file(statement: str, tactic: str = "prover_finish") -> str:
    """The single-file check body: header + statement + one native tactic."""
    options = SEARCH_OPTIONS if tactic == "prover_search" else ""
    return HEADER + options + _signature(statement) + "\n  " + tactic + "\n"


@dataclass
class Problem:
    id: str
    difficulty: str | None
    statement: str


def load_problems(path: Path) -> list[Problem]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        raw = raw.get("problems", [])
    problems = []
    for p in raw:
        problems.append(Problem(
            id=str(p.get("id", f"p{len(problems) + 1}")),
            difficulty=p.get("difficulty") or p.get("tier") or "unknown",
            statement=p["statement"],
        ))
    return problems


def run_baseline(
    problems: list[Problem],
    lean_dir: Path,
    tmp_dir: Path,
    tactic: str = "prover_finish",
    timeout: int = 120,
) -> dict:
    tmp_dir.mkdir(parents=True, exist_ok=True)
    solved: list[dict] = []
    unsolved: list[dict] = []
    t0 = time.time()
    for i, p in enumerate(problems, 1):
        f = tmp_dir / f"Baseline_{p.id}.lean"
        f.write_text(build_lean_file(p.statement, tactic), encoding="utf-8")
        ok, output = check_file(f, lean_dir, timeout=timeout)
        entry = {
            "id": p.id,
            "difficulty": p.difficulty,
            "statement": p.statement,
            "proved": ok,
            "output": "" if ok else output[-400:],
        }
        (solved if ok else unsolved).append(entry)
        print(f"[{i}/{len(problems)}] {p.id:<28} {'OK' if ok else 'FAIL'}",
              file=sys.stderr)
    return {
        "tactic": tactic,
        "total": len(problems),
        "solved": len(solved),
        "seconds": round(time.time() - t0, 2),
        "tiers": _tiers(solved, problems),
        "solved_ids": solved,
        "unsolved_ids": unsolved,
    }


def _tiers(solved: list[dict], all_problems: list[Problem]) -> dict[str, dict]:
    totals: dict[str, int] = defaultdict(int)
    for p in all_problems:
        totals[p.difficulty] += 1
    counts: dict[str, int] = defaultdict(int)
    for s in solved:
        counts[s["difficulty"]] += 1
    return {
        d: {"solved": counts[d], "total": totals[d]}
        for d in totals
    }


def print_report(report: dict) -> None:
    print(f"\ntactic:       {report['tactic']}")
    print(f"total:        {report['total']}")
    print(f"solved:       {report['solved']}  ({report['solved'] / report['total']:.0%})")
    print(f"wall time:    {report['seconds']}s")
    print("\nper tier:")
    for tier, v in sorted(report["tiers"].items()):
        pct = v["solved"] / v["total"] if v["total"] else 0
        print(f"  {tier:<10} {v['solved']:>3}/{v['total']:<3} ({pct:.0%})")
    print("\nsolved ids:")
    print("  " + " ".join(s["id"] for s in report["solved_ids"]) or "  (none)")
    print("\nunsolved ids:")
    print("  " + " ".join(s["id"] for s in report["unsolved_ids"]) or "  (none)")


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--problems", default="benchmark/problems.json",
                    help="benchmark JSON file (list of {id,difficulty,statement})")
    ap.add_argument("--out", default="benchmark/lean_baseline.json",
                    help="JSON report path")
    ap.add_argument("--tactic", default="prover_finish",
                    help="native tactic to try (prover_finish | prover_search)")
    ap.add_argument("--timeout", type=int, default=120,
                    help="per-problem Lean timeout (seconds)")
    ap.add_argument("--start", type=int, default=1,
                    help="resume from problem N (1-indexed)")
    args = ap.parse_args(argv)

    from pathlib import Path

    from .loop import LEAN_DIR

    problems = load_problems(Path(args.problems))
    if not problems:
        print("no problems found", file=sys.stderr)
        return 1
    problems = problems[args.start - 1:]

    print(f"baseline: {len(problems)} problems, tactic={args.tactic}, "
          f"lean_dir={LEAN_DIR}", file=sys.stderr)
    report = run_baseline(problems, LEAN_DIR, LEAN_DIR / "tmp",
                          tactic=args.tactic, timeout=args.timeout)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print_report(report)
    print(f"\nreport written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
