#!/usr/bin/env python3
"""Import standard theorem-proving benchmarks into prover format.

Currently supports the MiniF2F Lean 4 port
(https://github.com/yangky11/miniF2F-lean4), whose statements are written as
``theorem ... := by sorry`` with a uniform preamble::

    set_option maxHeartbeats 0
    open BigOperators Real Nat Topology Rat

Every imported statement is re-checked against the *pinned* Mathlib in
``../lean`` (our toolchain, Lean v4.20.0 — the port targets v4.24.0), so a
statement that no longer type-checks on our stack is flagged
``"compiles": false`` with the first diagnostics, instead of being silently
dropped. That keeps the benchmark honest: scores are only meaningful over the
subset that compiles on our pinned Mathlib.

Usage::

    python benchmark/import_standard.py minif2f \
        --src <dir containing MiniF2F/> --split test --verify
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agent import lean
from agent.loop import HEADER, LEAN_DIR

SORRY = " := by\n  sorry"
NAME_RE = re.compile(r"^theorem\s+([A-Za-z0-9_']+)")
VERIFY_TAG = "minif2f_import"


def parse_problem_file(path: Path) -> dict:
    """Parse one MiniF2F problem file into prover-format problem dict.

    Keeps the preamble (set_option / open) so the statement type-checks with
    our header; drops ``import`` lines (re-added by the agent header) and any
    comment lines. Renames the theorem with the ``prover_`` prefix to mirror
    gen_problems.py and guarantee no collision with a Mathlib declaration.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    th_idx = [i for i, l in enumerate(lines) if l.strip().startswith("theorem ")]
    if len(th_idx) != 1:
        raise ValueError(f"{path.name}: expected exactly one theorem, found {len(th_idx)}")
    th_idx = th_idx[0]

    preamble = []
    in_block = False
    for l in lines[:th_idx]:
        s = l.strip()
        if in_block:
            if "-/" in s:
                in_block = False
            continue
        if s.startswith("/-"):
            if "-/" not in s:
                in_block = True
            continue
        if not s or s.startswith(("import ", "--")):
            continue
        preamble.append(s)

    sig_lines = []
    for l in lines[th_idx:]:
        sig_lines.append(l.rstrip())
        if ":=" in l:
            break

    m = NAME_RE.match(sig_lines[0])
    if not m:
        raise ValueError(f"{path.name}: cannot parse theorem name from {sig_lines[0]!r}")
    name = m.group(1)

    sig = "\n".join(sig_lines)
    sig = sig[: sig.index(":=")].rstrip()
    sig = sig.replace(f"theorem {name}", f"theorem prover_{name}", 1)

    parts = []
    if preamble:
        parts.append("\n".join(preamble))
    parts.append(sig + SORRY)

    return {
        "id": f"minif2f_{name}",
        "difficulty": "",  # filled in by import_minif2f
        "statement": "\n\n".join(parts),
        "source": "minif2f",
        "source_name": name,
    }


def import_minif2f(src_dir: Path, split: str, limit: int | None = None) -> list[dict]:
    """Import every problem in ``<src_dir>/MiniF2F/<Split>/*.lean``."""
    subdir = src_dir / "MiniF2F" / split.capitalize()
    if not subdir.is_dir():
        raise FileNotFoundError(f"expected split directory at {subdir}")
    files = sorted(subdir.glob("*.lean"))
    if limit is not None:
        files = files[:limit]
    problems = []
    for f in files:
        p = parse_problem_file(f)
        p["difficulty"] = f"minif2f_{split}"
        problems.append(p)
    return problems


def verify(problems: list[dict], lean_dir: Path, timeout: int = 180) -> list[dict]:
    """Type-check every statement against our pinned Mathlib.

    Tolerates ``sorry`` (compile_only): ``compiles`` is true iff the file
    exits 0. Non-compiling entries keep their first diagnostics so nothing is
    silently dropped. Returns a new list; input is not mutated.
    """
    checked = []
    tmp_dir = lean_dir / "tmp"
    tmp_dir.mkdir(exist_ok=True)
    for i, p in enumerate(problems):
        tmp = tmp_dir / f"{VERIFY_TAG}_{i}.lean"
        tmp.write_text(HEADER + p["statement"] + "\n", encoding="utf-8")
        rc, out = lean.compile_only(tmp, lean_dir, timeout=timeout)
        tmp.unlink(missing_ok=True)
        p2 = dict(p)
        p2["compiles"] = rc == 0
        p2["error"] = "" if rc == 0 else lean.error_report(lean_dir, out, max_diags=3)
        checked.append(p2)
    return checked


def _write(path: Path, problems: list[dict]) -> None:
    path.write_text(json.dumps(problems, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def cmd_minif2f(args: argparse.Namespace) -> int:
    problems = import_minif2f(Path(args.src), args.split, limit=args.limit)
    print(f"parsed {len(problems)} problems ({args.split})")

    if args.verify:
        problems = verify(problems, Path(args.lean_dir), timeout=args.timeout)
        ok = sum(1 for p in problems if p["compiles"])
        bad = [p["id"] for p in problems if not p["compiles"]]
        print(f"compile check: {ok}/{len(problems)} type-check on our Mathlib")
        if bad:
            print(f"non-compiling ({len(bad)}): {', '.join(bad[:10])}{' ...' if len(bad) > 10 else ''}")

    dest = Path(args.dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    _write(dest, problems)
    print(f"wrote {dest}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    mf = sub.add_parser("minif2f", help="import MiniF2F Lean4 port")
    mf.add_argument("--src", required=True, help="directory containing MiniF2F/")
    mf.add_argument("--split", choices=["test", "valid"], default="test")
    mf.add_argument("--limit", type=int, default=None, help="only import first N problems")
    mf.add_argument("--dest", default=None, help="output JSON (default benchmark/minif2f_<split>.json)")
    mf.add_argument("--verify", action="store_true", help="type-check against our pinned Mathlib")
    mf.add_argument("--lean-dir", default=str(LEAN_DIR), help="lean project dir")
    mf.add_argument("--timeout", type=int, default=180, help="per-file lean timeout (s)")
    mf.set_defaults(fn=cmd_minif2f)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "minif2f" and args.dest is None:
        args.dest = str(Path(__file__).parent / f"minif2f_{args.split}.json")
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
