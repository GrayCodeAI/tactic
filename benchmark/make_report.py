#!/usr/bin/env python3
"""Assemble report.json from session JSONL logs (~/.prover/sessions/).

Use after a bench run (especially if the process was interrupted before it
could write the report, e.g. a hung worker): reconstructs per-problem results
with full traces from the durable session files.
"""

import json
import sys
from pathlib import Path

PROBLEMS = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("benchmark/problems.json")
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("report.json")
SESSIONS = Path.home() / ".prover" / "sessions"
TIER = {"trivial": 0, "easy": 1, "medium": 2, "hard": 3}


def latest_session(pid: str) -> Path | None:
    files = sorted(SESSIONS.glob(f"*{pid}.jsonl"))
    return files[-1] if files else None


def load(path: Path) -> list[dict]:
    recs = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            try:
                recs.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return recs


def main() -> None:
    problems = json.loads(PROBLEMS.read_text())
    results = []
    missing = []
    for p in problems:
        sp = latest_session(p["id"])
        if sp is None:
            missing.append(p["id"])
            continue
        recs = load(sp)
        start = next((r for r in recs if r.get("event") == "start"), {})
        result = next((r for r in recs if r.get("event") == "result"), None)
        if result is None:
            missing.append(p["id"])
            continue
        results.append({
            "id": p["id"],
            "proved": result.get("proved", False),
            "steps": result.get("steps", 0),
            "seconds": result.get("seconds", 0),
            "tokens": result.get("total_tokens", 0),
            "prompt_tokens": result.get("prompt_tokens", 0),
            "completion_tokens": result.get("completion_tokens", 0),
            "cost_usd": result.get("cost_usd", 0.0),
            "session": str(sp),
            "trace": recs,
        })

    # keep original problem order
    order = {p["id"]: i for i, p in enumerate(problems)}
    results.sort(key=lambda r: order[r["id"]])

    solved = sum(1 for r in results if r["proved"])
    total_tokens = sum(r["tokens"] for r in results)
    total_cost = sum(r["cost_usd"] for r in results)
    model = "?"
    for r in results:
        start = next((x for x in r["trace"] if x.get("event") == "start"), None)
        if start and start.get("model"):
            model = start["model"]
            break
    report = {
        "score": solved,
        "total": len(problems),
        "attempted": len(results),
        "total_tokens": total_tokens,
        "total_cost_usd": round(total_cost, 6),
        "model": model,
        "results": results,
    }
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False))

    by_tier: dict[str, dict] = {}
    res_by_id = {r["id"]: r for r in results}
    for p in problems:
        t = by_tier.setdefault(p["difficulty"], {"proved": 0, "total": 0})
        t["total"] += 1
        r = res_by_id.get(p["id"])
        if r and r["proved"]:
            t["proved"] += 1
    print(f"score: {solved}/{len(problems)} (attempted {len(results)})")
    for tier, v in sorted(by_tier.items(), key=lambda kv: TIER.get(kv[0], 9)):
        print(f"  {tier:>7}: {v['proved']}/{v['total']}")
    print(f"tokens: {total_tokens}  cost: ${total_cost:.4f}")
    if missing:
        print(f"MISSING ({len(missing)}): {missing}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
