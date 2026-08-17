#!/usr/bin/env bash
# Wait for retry2 bench, merge into report.json, log results.
set -u
REPO="${1:-/home/lpatel/Code/tactic}"
cd "$REPO" || exit 1
while ! pgrep -f "tactic bench --problems benchmark/retry2.json" >/dev/null; do sleep 30; done
while pgrep -f "tactic bench --problems benchmark/retry2.json" >/dev/null; do sleep 60; done
if [ -f report-retry2.json ]; then
  source .venv/bin/activate
  python3 benchmark/merge_reports.py report-retry2.json report.json > merge-results2.log 2>&1
  echo "merged." >> merge-results2.log
else
  echo "report-retry2.json not found" >> merge-results2.log
fi
