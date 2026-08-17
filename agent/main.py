"""CLI entry point: `tactic prove ...` / `tactic bench ...`."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import sys

# Unbuffered stdout so background runs (nohup ... > log) show progress live.
sys.stdout.reconfigure(line_buffering=True)

from .loop import prove


def cmd_prove(args: argparse.Namespace) -> int:
    print(f"Proving:\n{args.statement}\n")
    r = prove(args.statement, max_steps=args.max_steps, goal_feedback=not args.no_goal_feedback)
    print(f"\nproved={r.proved} steps={r.steps} time={r.seconds:.1f}s")
    print(f"tokens: {r.total_tokens} (prompt={r.total_prompt_tokens}, completion={r.total_completion_tokens}) cost≈${r.estimated_cost_usd:.6f}")
    if r.proved:
        print("\n" + r.proof)
    return 0 if r.proved else 1


def _prove_one(p: dict, max_steps: int, idx: int, total: int, goal_feedback: bool = True) -> tuple[dict, int, float]:
    """Prove a single problem. Returns (result_dict, tokens, cost)."""
    print(f"[{idx}/{total}] {p['id']}: {p['statement'][:70]}...")
    r = prove(p["statement"], max_steps=max_steps, verbose=False, problem_id=p["id"], goal_feedback=goal_feedback)
    result = {
        "id": p["id"],
        "proved": r.proved,
        "steps": r.steps,
        "seconds": round(r.seconds, 1),
        "tokens": r.total_tokens,
        "prompt_tokens": r.total_prompt_tokens,
        "completion_tokens": r.total_completion_tokens,
        "cost_usd": round(r.estimated_cost_usd, 6),
        "trace": r.trace,
    }
    cost_str = f" cost≈${r.estimated_cost_usd:.6f}" if r.total_tokens else ""
    print(f"    -> {'PROVED' if r.proved else 'FAILED'} in {r.steps} steps ({r.total_tokens} tokens{cost_str})")
    return result, r.total_tokens, r.estimated_cost_usd


def cmd_bench(args: argparse.Namespace) -> int:
    from pathlib import Path

    problems = json.loads(Path(args.problems).read_text())
    start = args.start - 1  # 1-indexed for humans
    problems = problems[start:]
    results = []
    total_tokens = 0
    total_cost = 0.0

    goal_feedback = not args.no_goal_feedback

    if args.parallel and args.parallel > 1:
        print(f"Running {len(problems)} problems in parallel (workers={args.parallel})...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.parallel) as executor:
            futures = [
                executor.submit(_prove_one, p, args.max_steps, i, len(problems), goal_feedback)
                for i, p in enumerate(problems, start + 1)
            ]
            for fut in concurrent.futures.as_completed(futures):
                result, tokens, cost = fut.result()
                results.append(result)
                total_tokens += tokens
                total_cost += cost
    else:
        for i, p in enumerate(problems, start + 1):
            result, tokens, cost = _prove_one(p, args.max_steps, i, len(problems), goal_feedback)
            results.append(result)
            total_tokens += tokens
            total_cost += cost

    # Sort results by original problem order
    id_order = {p["id"]: i for i, p in enumerate(problems)}
    results.sort(key=lambda r: id_order.get(r["id"], 0))

    solved = sum(1 for r in results if r["proved"])
    print(f"\nScore: {solved}/{len(results)}")
    print(f"Total tokens: {total_tokens}, estimated cost: ${total_cost:.6f}")
    if args.report:
        Path(args.report).write_text(json.dumps({"score": solved, "total": len(results), "total_tokens": total_tokens, "total_cost_usd": round(total_cost, 6), "results": results}, indent=2))
        print(f"Report written to {args.report}")
    return 0


def cmd_mcp(args: argparse.Namespace) -> int:
    from .mcp import serve

    return serve()


BOARD_FILE = "leaderboard.json"


def load_board() -> list[dict]:
    from pathlib import Path

    p = Path(BOARD_FILE)
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return []


def cmd_leaderboard(args: argparse.Namespace) -> int:
    from datetime import datetime, timezone
    from pathlib import Path

    board = load_board()
    if not args.show and args.run:
        from .loop import prove

        problems = json.loads(Path(args.problems).read_text())
        results = []
        for i, p in enumerate(problems, 1):
            print(f"[{i}/{len(problems)}] {p['id']}")
            r = prove(p["statement"], max_steps=args.max_steps, verbose=False, problem_id=p["id"])
            results.append({"id": p["id"], "difficulty": p["difficulty"], "proved": r.proved})
        score = sum(1 for r in results if r["proved"])
        by_tier: dict[str, dict] = {}
        for r in results:
            t = by_tier.setdefault(r["difficulty"], {"proved": 0, "total": 0})
            t["total"] += 1
            t["proved"] += int(r["proved"])
        entry = {
            "name": args.name or os.environ.get("TACTIC_MODEL", "unknown"),
            "score": score,
            "total": len(results),
            "tiers": by_tier,
            "max_steps": args.max_steps,
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        }
        board.append(entry)
        board.sort(key=lambda e: -e["score"])
        Path(BOARD_FILE).write_text(json.dumps(board, indent=2) + "\n")
        print(f"\nRecorded: {entry['name']} {score}/{len(results)} → {BOARD_FILE}")
        return 0

    if not board:
        print("Leaderboard is empty. Run `tactic leaderboard --run` after a benchmark.")
        return 0
    print(f"{'#':>2} {'name':<28} {'score':>5}  tiers")
    for i, e in enumerate(board, 1):
        tiers = " ".join(f"{t}:{v['proved']}/{v['total']}" for t, v in sorted(e.get("tiers", {}).items()))
        print(f"{i:>2} {e.get('name','?'):<28} {e.get('score',0):>3}/{e.get('total','?')}  {tiers}")
    return 0


def cli() -> None:
    ap = argparse.ArgumentParser(prog="tactic", description="Lean 4 proof agent")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("prove", help="prove a single theorem")
    p.add_argument("statement", help="Lean theorem statement (with proof or sorry)")
    p.add_argument("--max-steps", type=int, default=20)
    p.add_argument("--no-goal-feedback", action="store_true",
                   help="disable LSP goal-state feedback")
    p.set_defaults(fn=cmd_prove)

    b = sub.add_parser("bench", help="run the benchmark suite")
    b.add_argument("--problems", default="benchmark/problems.json")
    b.add_argument("--max-steps", type=int, default=20)
    b.add_argument("--start", type=int, default=1, help="resume from problem N (1-indexed)")
    b.add_argument("--report", default=None)
    b.add_argument("--parallel", type=int, default=1, help="number of parallel workers (default=1, sequential)")
    b.add_argument("--no-goal-feedback", action="store_true",
                   help="disable LSP goal-state feedback")
    b.set_defaults(fn=cmd_bench)

    m = sub.add_parser("mcp", help="run the MCP (Model Context Protocol) stdio server")
    m.set_defaults(fn=cmd_mcp)

    lb = sub.add_parser("leaderboard", help="record a benchmark score / show the board")
    lb.add_argument("--run", action="store_true",
                    help="run the benchmark first, then record the score")
    lb.add_argument("--problems", default="benchmark/problems.json")
    lb.add_argument("--max-steps", type=int, default=20)
    lb.add_argument("--name", default=None, help="entry name (default: model or env)")
    lb.add_argument("--show", action="store_true", help="only show current leaderboard")
    lb.set_defaults(fn=cmd_leaderboard)

    args = ap.parse_args()
    sys.exit(args.fn(args))


if __name__ == "__main__":
    cli()
