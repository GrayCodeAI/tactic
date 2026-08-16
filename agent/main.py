"""CLI entry point: `tactic prove ...` / `tactic bench ...`."""

from __future__ import annotations

import argparse
import json
import sys

from .loop import prove


def cmd_prove(args: argparse.Namespace) -> int:
    print(f"Proving:\n{args.statement}\n")
    r = prove(args.statement, max_steps=args.max_steps)
    print(f"\nproved={r.proved} steps={r.steps} time={r.seconds:.1f}s")
    if r.proved:
        print("\n" + r.proof)
    return 0 if r.proved else 1


def cmd_bench(args: argparse.Namespace) -> int:
    from pathlib import Path

    problems = json.loads(Path(args.problems).read_text())
    results = []
    for i, p in enumerate(problems, 1):
        print(f"[{i}/{len(problems)}] {p['id']}: {p['statement'][:70]}...")
        r = prove(p["statement"], max_steps=args.max_steps, verbose=False)
        results.append(
            {"id": p["id"], "proved": r.proved, "steps": r.steps, "seconds": round(r.seconds, 1)}
        )
        print(f"    -> {'PROVED' if r.proved else 'FAILED'} in {r.steps} steps")

    solved = sum(1 for r in results if r["proved"])
    print(f"\nScore: {solved}/{len(results)}")
    if args.report:
        Path(args.report).write_text(json.dumps({"score": solved, "total": len(results), "results": results}, indent=2))
        print(f"Report written to {args.report}")
    return 0


def cli() -> None:
    ap = argparse.ArgumentParser(prog="tactic", description="Lean 4 proof agent")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("prove", help="prove a single theorem")
    p.add_argument("statement", help="Lean theorem statement (with proof or sorry)")
    p.add_argument("--max-steps", type=int, default=20)
    p.set_defaults(fn=cmd_prove)

    b = sub.add_parser("bench", help="run the benchmark suite")
    b.add_argument("--problems", default="benchmark/problems.json")
    b.add_argument("--max-steps", type=int, default=20)
    b.add_argument("--report", default=None)
    b.set_defaults(fn=cmd_bench)

    args = ap.parse_args()
    sys.exit(args.fn(args))


if __name__ == "__main__":
    cli()
