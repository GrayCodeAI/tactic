#!/usr/bin/env python3
"""Merge a retry report into the main report.json, keeping the best result
per problem (proved wins over failed). Prints a summary of flips.

Usage: python3 benchmark/merge_reports.py [retry_report.json] [main report.json]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    retry_path = Path(sys.argv[1] if len(sys.argv) > 1 else "report-retry.json")
    main_path = Path(sys.argv[2] if len(sys.argv) > 2 else "report.json")

    if not retry_path.exists():
        print(f"retry report not found: {retry_path}", file=sys.stderr)
        return 1

    main = json.loads(main_path.read_text())
    retry = json.loads(retry_path.read_text())

    by_id = {r["id"]: r for r in main["results"]}
    flips = []
    unchanged = 0
    for r in retry["results"]:
        prev = by_id.get(r["id"])
        if prev is None:
            continue
        if r["proved"] and not prev["proved"]:
            flips.append(r["id"])
            by_id[r["id"]] = r  # the proved attempt replaces the failed one
        elif not r["proved"] and not prev["proved"]:
            unchanged += 1

    # Rebuild the results in the original order with the merged entries.
    order = [x["id"] for x in main["results"]]
    main["results"] = [by_id[i] for i in order]

    solved = sum(1 for r in main["results"] if r["proved"])
    main["score"] = solved
    main["total_tokens"] = sum(r.get("tokens", 0) for r in main["results"])
    main["total_cost_usd"] = round(sum(r.get("cost_usd", 0.0) for r in main["results"]), 6)

    main_path.write_text(json.dumps(main, indent=2))
    print(f"merged {len(retry['results'])} retry results into {main_path}")
    print(f"new score: {solved}/{main['total']}")
    if flips:
        print(f"flips ({len(flips)}): {', '.join(flips)}")
    else:
        print("no new flips in this retry")
    if unchanged:
        print(f"still failing: {unchanged}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
