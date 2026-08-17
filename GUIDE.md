# tactic — Full Guide

An agent that writes Lean 4 proofs. Give it a theorem; it loops
(LLM draft → `lake build` → parse errors → patch) until the proof
type-checks. Nothing counts as proved until Lean's kernel accepts it.

---

## 1. Install prerequisites

### Lean 4 toolchain (elan + lake)

```bash
curl https://elan.lean-lang.org/elan-init.sh -sSf | sh
source ~/.bashrc        # or restart your shell
lean --version
lake --version
```

### Mathlib (the math library — needed for ring/linarith/norm_num/Even/∑)

```bash
cd ~/Code/tactic/lean
lake update             # fetches mathlib (pinned to v4.20.0 in lakefile.toml)
lake exe cache get      # downloads prebuilt oleans (~10 min first time)
lake build              # verify it compiles
cd ..
```

> After this, each agent step compiles in seconds. Without the cache,
> every build would recompile Mathlib from source (~1 hour).

### Python agent

```bash
cd ~/Code/tactic
pip install -e .        # installs the `tactic` CLI
```

---

## 2. Configure the LLM

The agent speaks the OpenAI-compatible API. Free Qwen options (tested):

**TokenRouter (primary):**
```bash
export OPENAI_BASE_URL=https://api.tokenrouter.com/v1
export OPENAI_API_KEY=<your tokenrouter key>
export TACTIC_MODEL=qwen/qwen3.8-max-free
```

**HuggingFace endpoint (backup):**
```bash
export OPENAI_BASE_URL=https://g9hnto0u7lvbu837.us-east-2.aws.endpoints.huggingface.cloud/v1
export OPENAI_API_KEY=not-needed
export TACTIC_MODEL=Qwen/Qwen3.8-27B
```

Put these in `~/.bashrc` or a `.env` you source. Any OpenAI-compatible
endpoint works (DashScope, OpenRouter, Groq, local Ollama/vLLM).

---

## 3. First proof

```bash
tactic prove "theorem sq_nonneg (x : ℤ) : 0 ≤ x ^ 2 := by sorry"
```

What happens:
1. The statement is written to `lean/src/Tactic.lean` (with `import Mathlib` prepended)
2. `lake build` runs → fails on `sorry`
3. Diagnostics are parsed (file:line:col + surrounding source)
4. The LLM gets the errors and returns a corrected file
5. Repeat until `lake build` succeeds → **PROVED ∎**

Expected output:
```
Proving:
theorem sq_nonneg (x : ℤ) : 0 ≤ x ^ 2 := by sorry

  [step 1] 1 diagnostics
  [step 2] PROVED ∎

proved=True steps=2 time=14.3s

import Mathlib

open BigOperators Nat Finset

theorem sq_nonneg (x : ℤ) : 0 ≤ x ^ 2 := by
  exact sq_nonneg x
```

---

## 4. Run the benchmark

100 graded theorems in `benchmark/problems.json`:

| Tier | Count | Flavor |
|---|---|---|
| trivial | 20 | `add_comm`, `n - n = 0`, injectivity |
| easy | 30 | algebra identities, parity, gcd, lists |
| medium | 30 | Gauss sum, Pascal's rule, Bezout, mod arithmetic |
| hard | 20 | `30 ∣ n⁵−n`, Cauchy–Schwarz, four squares, Fermat two-squares |

```bash
# Full run (~1–3 hours depending on model speed)
tactic bench --max-steps 20 --report report.json

# Just the trivial tier while you validate the loop:
python3 -c "
import json
ps = json.load(open('benchmark/problems.json'))
json.dump([p for p in ps if p['difficulty']=='trivial'],
          open('benchmark/trivial.json','w'), indent=2)
"
tactic bench --problems benchmark/trivial.json --report report-trivial.json
```

`report.json` contains per-problem `{id, proved, steps, seconds}` plus the
score. That score is your leaderboard entry.

---

## 5. How the loop works (and why it works)

```
statement ──► LLM drafts proof ──► lake build ──► type-checks? ──► PROVED ∎
                    ▲                                │ no
                    └── parsed diagnostics ◄─────────┘
                        (error + source context)
```

The key insight: **Lean's compiler errors are machine-readable and precise.**
The LLM doesn't need to "know" it's right — it just needs to fix the exact
error Lean reports. This turns hallucination-prone generation into a
convergent repair loop. On top of that, the agent also feeds the model the
**open goal states** (via the Lean language server's `getInteractiveGoals`
RPC), so the model sees actual hypotheses + targets, not just error text.

Files:
- `agent/loop.py` — the loop, hammer pre-pass, resume/branch, result tracking
- `agent/events.py` — event protocol: one record stream fans out to trace/session/TUI
- `agent/session.py` — durable JSONL sessions (`~/.tactic/sessions/`, `tactic sessions`)
- `agent/session_manager.py` — session index (`index.jsonl`), resume history rebuild
- `agent/compaction.py` — folds old attempts into a failed-attempts summary
- `agent/lean.py` — `lake build` / `lake env lean` + diagnostic regex + source-context
- `agent/llm.py` — OpenAI-compatible client, ```lean block extraction, cost tracking
- `agent/lsp.py` — Lean language server client (goal-state feedback)
- `agent/mcp.py` — MCP server (expose `prove_theorem` to any agent)
- `agent/commands.py` — slash-command registry (`/help` `/branch` `/theme` `/new` `/compact` `/name`, …)
- `agent/autocomplete.py` — slash-command completions
- `agent/themes.py` — TUI themes (`/theme`, custom in `~/.tactic/themes/*.json`)
- `agent/terminal_title.py` — terminal tab title + braille spinner while running
- `agent/terminal_notification.py` — OSC 9/99 desktop notification on run end
- `agent/session_stats.py` — per-session token/step/cost totals
- `agent/tui.py` — Textual TUI (browse problems, live proof trace, replay, commands)
- `agent/main.py` — CLI (`prove` / `bench` / `tui` / `mcp` / `sessions` / `leaderboard`)

## 5b. The TUI

`tactic tui` (add `-p 4` for parallel workers). Panel layout: problem list,
log, goals, errors, proof. Keymap: `p` prove selected · `c` custom theorem ·
`r` run remaining · `w` workers · `s` stop · `v` sessions · `l` leaderboard ·
`ctrl+k` command palette · `ctrl+e` edit last queued prompt · `q` quit.

While a run is active, plain text typed in the prompt bar is queued and
proved automatically when the run finishes (ctrl+e pulls the last queued one
back for editing). On completion, a desktop notification is attempted
(`TACTIC_NOTIFICATION=auto|bell|off`; OSC 9/99 for kitty/ghostty/iTerm).

Slash commands in the prompt bar (complete with `ctrl+space`):

```
/help /status /clear /stop /run /new /compact /quit
/prove [<statement>]        prove a custom theorem (editor modal or inline)
/workers <n>                parallel proof workers
/resume                     browse sessions (picker) · replay one
/branch <session> [turn]    re-run a theorem from an earlier turn (model summarizes
                            the old branch first; TACTIC_BRANCH_SUMMARY=0 disables)
/name <new name>            rename the most recent session
/export <path>              save the session transcript (html/jsonl by suffix)
/prompts                    pick a markdown prompt template to apply
/theme [name]               tactic-dark / tactic-light / high-contrast
/model /system /hotkeys     show model / loop system prompt / keymap
```

Prompt templates are markdown files in `~/.tactic/prompts/` or
`<project>/.tactic/prompts/` (project wins, `TACTIC_PROMPTS_DIR` overrides).
Typing `/name args` for an unknown command expands the template; `{{ args }}`
or `{{ arguments }}` receives the arguments. Templates named `prompts`,
`skills`, `tools`, `reload` are reserved.

Selecting text in any panel copies it (auto-copy in session replay with
OSC-52 via pyperclip/terminal when available). Sessions are durable under
`~/.tactic/sessions/`; resuming one seeds the repair loop with the old
attempts so it doesn't repeat the same dead ends.

---

## 6. Tuning

- `--max-steps N` — iteration budget per theorem (default 20). Weak models
  need more; strong models usually finish in ≤5.
- `TACTIC_MODEL` — bigger model = fewer steps, higher quality. For
  proof-writing, 235B-class >> 27B-class >> 7B-class.
- History is compacted (not truncated): once it passes 18 turns, old attempts are folded into a failed-attempts summary so the model stops re-trying dead ends (last 12 turns stay verbatim).
- Temperature is fixed at 0.2 in `agent/llm.py` (proofs want determinism).

---

## 7. Troubleshooting

| Symptom | Fix |
|---|---|
| `lake: command not found` | `source ~/.bashrc` after elan install |
| Build takes forever | You skipped `lake exe cache get` |
| `unknown identifier 'Even'` etc. | Mathlib import missing — check `HEADER` in `agent/loop.py` |
| LLM returns prose, no code block | Model too weak; or check `extract_lean_code` output |
| API 429 / overloaded | Free tiers rate-limit; switch provider or add backoff |
| Proof uses `sorry` and "passes" | Can't happen — `lake build` fails on `sorry` by default |

---

## 8. Roadmap

- [x] Core loop + error parsing with source context
- [x] 100-problem graded benchmark
- [x] Mathlib wiring
- [x] Hammer pre-pass (`ring`/`omega`/`linarith`/… before spending LLM tokens)
- [x] Proof-trace logging + token/cost tracking per problem
- [x] Per-problem file isolation → parallel benchmark runs (`--parallel N`)
- [x] Goal-state feedback (not just errors) via Lean LSP (`getInteractiveGoals`)
- [x] MCP server wrapper (`tactic mcp` — tools: prove_theorem, benchmark_score, problems)
- [x] Local leaderboard (`tactic leaderboard --run --show`)
- [x] TUI: custom prove, session replay, parallel workers, Errors panel
- [x] Clipboard (tau port: pyperclip + OSC-52 fallback, selection-aware)
- [x] Slash commands (`/help` `/prove` `/branch <id> [turn]` …, tau pattern)
- [x] Session resume + branching (index.jsonl, prove --resume from, branch_at)
- [x] History compaction (failed-attempts summary, tau memory model)
- [ ] Public leaderboard + first results post


---

## 9. The play after it works

1. Run the trivial tier → post the score publicly (X/HN/Lean Zulip)
2. Iterate the loop, climb the tiers in public
3. At ~60–70/100 you have a credible result → talk to FutureHouse,
   Harmonic, Sakana, frontier-lab math teams
4. Branch: job offer, seed round, or productize (proof-checking API)
