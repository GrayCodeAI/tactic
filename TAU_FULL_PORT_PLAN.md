# TAU → lean-prover Full-Fidelity Port Plan — Phases 12-16
*Generated 2026-08-20 · Tau commit `37a9e43` (96 files · ~42 kLOC) vs lean-prover `agent/` (51 files · ~9 830 LOC) · Prior work: Batches 7-11 delivered lightweight stubs (extensions 2391→24 LOC, oauth 1388→14 LOC, rpc 798→7 LOC)*

> **Goal:** 1:1 full-fidelity port of every remaining Tau file — no stubs. Lean-adaptation must be explicit (full port vs Lean-shim) and preserve Tau semantics, event contracts, and resource/trust boundaries.

---

## Table of Contents
1. [Inventory Method & Stub Taxonomy](#1-inventory-method--stub-taxonomy)
2. [Complete Remaining-File Inventory (72 files, ~32 kLOC gap)](#2-complete-remaining-file-inventory)
3. [Phase Overview & Dependency DAG](#3-phase-overview--dependency-dag)
4. [Phase 12 — Agent Core (tau_agent)](#4-phase-12--agent-core)
5. [Phase 13 — Provider Fleet (tau_ai)](#5-phase-13--provider-fleet)
6. [Phase 14 — Coding Session Substrate](#6-phase-14--coding-session-substrate)
7. [Phase 15 — Extensions + OAuth + RPC](#7-phase-15--extensions--oauth--rpc)
8. [Phase 16 — TUI + Rendering + CLI + Misc](#8-phase-16--tui--rendering--cli--misc)
9. [Lean-Incompatible Features — Port vs Shim Matrix](#9-lean-incompatible-features)
10. [File-by-File Mapping (Tau → lean-prover, new LOC)](#10-file-by-file-mapping)
11. [Effort, Risk, Verification](#11-effort-risk-verification)
12. [Checklists & Definition of Done](#12-checklists)

---

## 1. Inventory Method & Stub Taxonomy

**Counts verified with `wc -l`:**

*   Tau: 96 files under `src/tau_agent|tau_ai|tau_coding` → 42 023 LOC (bash `wc -l` over all `*.py` in those roots, data/docs excluded).
*   lean-prover `agent/*.py`: 32 source files → 9 830 LOC. Dir `agent/` on disk shows 51 entries including `__pycache__`.

**Stub detection:** `grep` for Tau symbols + `wc -l` delta. Classified as:

| Tag | Meaning | Example |
|-----|---------|---------|
| **STUB** | File exists in lean-prover but <15% of Tau LOC and <20% of public API | `agent/extensions.py` 24 LOC vs Tau 2391 LOC (1.0%) |
| **PARTIAL** | File exists, 20-60% LOC, missing branches (e.g. no grouped/batched tools) | `agent/tui.py` 2055 LOC vs Tau `tui/app.py 7128+widgets 2604+state 918` = 10 650 LOC (19%) |
| **SKIPPED** | No counterpart in lean-prover | `tau_coding/image_processing.py`, `tau_ai/anthropic.py` |

*Batches 7-11 stubs to upgrade:*

```
extensions: tau 2391 (api 1001 + runtime 943 + loader 350 + __init__ 97) → lean 24
oauth:      tau 1388 (oauth 527 + anthropic 285 + github 285 + device 109 + registry 55 + types 127) → lean 14
rpc:        tau 798 → lean 7  (delegates to mcp.py)
tools:      tau 1215 → lean 77 (only 3 thin wrappers)
session:    tau 3389 (+42 storage +111 jsonl etc) → lean 94
providers:  tau provider_config 2563 + catalog 111 + catalog_loader 681 + runtime 349 → lean 19 + 16
tui:        tau ~10.6k → lean 2055
```

---

## 2. Complete Remaining-File Inventory

> Every file below still requires work for full fidelity. Grouped by package. For each: `Tau LOC | lean-prover LOC | gap | status`.

### 2A. `src/tau_agent` — Portable Agent Brain (2 383 LOC total)

| # | Tau file | LOC | lean file | lean LOC | Gap | Purpose | Lean Adaptation | Complexity | Implementation Steps |
|---|----------|-----|-----------|----------|-----|---------|---------------|------------|----------------------|
| A1 | `tau_agent/loop.py` | 328 | `agent/loop.py` | 734 | **Divergent, not 1:1** | Pure Pi provider/tool loop (`run_agent_loop`, `BeforeToolCall/AfterToolCall`, `pending steer/follow_up`, `max_turns`, `repair_tool_history`) | **Rewrite**: lean-prover `loop.py` is Lean-specific `prove()` loop (hammers, LSP, corpus). Must **co-exist**: rename current `prove` loop to `agent/prover_loop.py`, implement Tau `run_agent_loop` verbatim in `agent/loop.py` and make `prove()` call it via a `LeanToolHarness` provider. | High | 1. Port `tau_agent/loop.py` verbatim (keep `get_steering_messages`/`get_follow_up_messages` seams). 2. Add `agent/provider.py` (CancellationToken interface). 3. Wire `repair_tool_history` from `tool_history.py`. 4. Add tests mirroring `tests/tau_agent/test_loop.py`. |
| A2 | `tau_agent/harness.py` | 259 | `agent/harness.py` | 15 | 244 | `AgentHarness` — stateful wrapper over `run_agent_loop` (queues, `is_running`, `subscribe`, `cancel`, `replace_messages`, `steer/follow_up`) | Direct port; lean-prover currently a dataclass stub shimming `prove`. | Med | 1. Port `HarnessConfig` + `QueuedMessages` dataclasses. 2. Implement `AgentHarness` with async iterator fan-out (anyio-style but `asyncio` for lean). 3. Add storage-backed tests. |
| A3 | `tau_agent/messages.py` | 278 | `agent/messages.py` | 9 | 269 | `AgentMessage` hierarchy (`UserMessage`, `AssistantMessage` with `ThinkingContent`/`TextContent`/`ToolCall`, `ToolResultMessage`, `CustomMessage`, `BranchSummaryMessage`, `CompactionSummaryMessage`) | Full port — lean uses `history: list[dict]` not typed messages. | High | 1. Port Pydantic models (or dataclasses with `model_copy`). Keep `message_text()` helper. 2. Update `loop.py` to use typed messages not dicts. 3. Add `messages_have_images` parity. |
| A4 | `tau_agent/provider.py` | 37 | *(none — embedded in llm.py)* | 0 | 37 | `ModelProvider` protocol `stream_response()` + `CancellationToken` | Direct port | Low | Port `CancellationToken` (`is_cancelled`, `cancel`) + `ModelProvider` ABC. |
| A5 | `tau_agent/provider_events.py` | 107 | *(none)* | 0 | 107 | Typed provider→agent bridge `AssistantStart/Done/Error/TextDelta` | Direct port | Low | Port verbatim; ensure `tau_ai` providers emit these. |
| A6 | `tau_agent/events.py` | 87 | `agent/events.py` | 66 | 21 partial | Agent lifecycle events `AgentStart/End`, `TurnStart/End`, `MessageStart/Update/End`, `ToolExecution*` | **PARTIAL** — lean events are proof-centric (`hammer`, `build`, `goals`). Must merge: keep proof events, add Tau `AgentEvent` union `type` field parity. | Med | 1. Extend `agent/events.py` with Tau `AgentEvent` hierarchy (keep existing `record()`/`format()` for prove trace). 2. Add `isinstance` guards. |
| A7 | `tau_agent/tools.py` | 118 | `agent/tools.py` | 77 | 41 partial | `AgentTool` (name/label/description/parameters/`execute_fn`/`prompt_snippet`/`render_call`/`render_result`), `AgentToolResult`, `ToolCancellationToken` | Full port — lean `AgentTool` lacks `label`/`prompt_*`/`render_*`, uses `Callable[[dict],dict]` not Tau's `ToolCall`-keyed async executor. | Med | 1. Port `ToolDefinition` separation (keep lean `AgentTool` as compat shim). 2. Add `ToolCancellationToken`, `ToolUpdateCallback`, `execution_mode`. 3. Migrate `lean_check_tool` etc to `ToolDefinition.to_agent_tool()`. |
| A8 | `tau_agent/tool_history.py` | 169 | *(none)* | 0 | 169 | `repair_tool_history()` — fixes orphaned tool_calls/results across compaction/branch | Direct port (critical for resumption) | Med | Port `ToolHistoryRepair` dataclass + `repair_tool_history(messages) -> RepairResult`. Add property tests. |
| A9 | `tau_agent/types.py` | 8 | *(none)* | 0 | 8 | `JSONValue` alias | Trivial | Low | `JSONValue = str|int|float|bool|None|dict|list` typing alias in `agent/types.py`. |
| A10 | `tau_agent/session/__init__.py` | 50 | `agent/session.py` | 94 | divergent | Re-exports `SessionState`, `SessionEntry` tree types | Merge — lean `session.py` is flat JSONL log (`Session`, `read_session`, `list_sessions`). Tau `SessionState.from_entries`, leaf/branch model is missing. | High | 1. Create `agent/session/` package (see storage section). 2. Keep lean `sessions_dir()` alias. |
| A11 | `tau_agent/session/entries.py` | 117 | *(none)* | 0 | 117 | `SessionEntry` union: `MessageEntry`, `CompactionEntry`, `BranchSummaryEntry`, `CustomEntry`, `LabelEntry`, `LeafEntry`, etc. | Direct port (Pydantic `BaseModel` with `type` discriminator) | Med | Port all entry types; ensure `branch_summary` compaction interop. |
| A12 | `tau_agent/session/jsonl.py` | 111 | *(in session.py 20 lines)* | 0 | ~90 | `entries_from_json_lines`/`entry_to_json_line` (U+2028-safe split) | Direct port | Low | Port JSONL codec with `\n`-only split note. |
| A13 | `tau_agent/session/memory.py` | 136 | *(none)* | 0 | 136 | `MemorySessionStorage` (in-memory for tests) | Direct port | Low | Port `InMemoryStorage(acts as SessionStorage)`. |
| A14 | `tau_agent/session/storage.py` | 42 | *(none — logic in session.py)* | 0 | 42 | `SessionStorage` Protocol + `JsonlSessionStorage` | **PARTIAL** — lean `Session(path=open/write)` is sync + caller-owned. Tau `storage.py` is async `append`/`read_all` with atomic `mkdir`. | Low | 1. Create `agent/session/storage.py` with `SessionStorage` + `JsonlSessionStorage` (async). 2. Adapt lean `Session` to wrap it or keep both. |
| A15 | `tau_agent/session/tree.py` | 40 | *(none — in loop.py `history_from_records`)* | 0 | 40 | `path_to_entry`, `SessionTreeError`, leaf resolution | Direct port | Low | Port tree path helpers; merge with `agent/branch_summary.py`. |

### 2B. `src/tau_ai` — Provider Fleet (4 494 LOC total)

| # | Tau file | LOC | lean file | lean LOC | Gap | Purpose | Lean Adaptation | Complexity | Steps |
|---|----------|-----|-----------|----------|-----|---------|-----------------|------------|-------|
| B1 | `tau_ai/openai_compatible.py` | 1364 | `agent/llm.py` | 249 | **~1100** | Chat vs Responses routing, streaming parsers, SSE, reasoning_effort, image attachment fallback, retry | **High** — lean `llm.py` uses sync `OpenAI` SDK. Must replace with async `httpx` streaming parity (or keep sync shim but add `stream_response()` async generator). | High | 1. Create `agent/providers/openai_compatible.py` porting `_ChatStreamParser`, `_ResponsesStreamParser`, `_build_chat_payload`. 2. Add `supports_images` flag via `content.py`. 3. Wire `CancellationToken` + `retry.py` via httpx. 4. Keep lean `llm.chat()` as compat wrapper that drains `stream_response()`. |
| B2 | `tau_ai/openai_codex.py` | 1080 | *(none)* | 0 | 1080 | Codex `openai-codex-responses` (OAuth `auth.base_url` override, session affinity `session_id`, reasoning summary) | **Lean shim**: lean rarely uses Codex subscription; port fully but default to API-key path; OAuth `credential_resolver` seam must work when `agent/oauth` is full. | High | Port `OpenAICodexProvider`; share `_stream` envelope with compatible file. |
| B3 | `tau_ai/anthropic.py` | 771 | *(none — dict stub in providers.py)* | 0 | 771 | Claude Messages API (`thinking` budgets, tool use, compat `sendSessionAffinityHeaders`) | Full port under `agent/providers/anthropic.py`. Lean currently maps Anthropic via OpenRouter. | High | Port `AnthropicConfig`, `AnthropicProvider.stream_response`, tool arg coercion. |
| B4 | `tau_ai/google.py` | 493 | *(none — dict stub)* | 0 | 493 | Gemini `google-generative-ai` (function declarations, `googleGenerativeAI` compat) | Full port | Med | `agent/providers/google.py`; add `google-generative-ai` payload builder. |
| B5 | `tau_ai/mistral.py` | 525 | *(none — dict stub)* | 0 | 525 | Mistral Conversations API | Full port | Med | `agent/providers/mistral.py`. |
| B6 | `tau_ai/stream.py` | 212 | *(none)* | 0 | 212 | `canonicalize_provider_stream()` — normalizes `ProviderEvent` → `AssistantMessageEvent` | Direct port | Med | `agent/stream.py`; covers reasoning/thinking merge, tool_call ID portability. |
| B7 | `tau_ai/_provider_events.py` | 93 | *(none)* | 0 | 93 | `ProviderResponseStart/End`, `ProviderTextDelta`, `ProviderThinkingDelta`, `ProviderToolCallEvent`, `ProviderErrorEvent` | Direct port | Low | `agent/provider_events.py` (or `tau_ai_/` namespaced). |
| B8 | `tau_ai/content.py` | 45 | *(none — ad-hoc in llm.py)* | 0 | 45 | `text_and_images()`, `messages_have_images()`, placeholder strings | Direct port | Low | `agent/content.py`. |
| B9 | `tau_ai/env.py` | 157 | *(none)* | 0 | 157 | `OpenAICompatibleConfig`, `AnthropicConfig`, compat dicts (`supportsPromptCacheKey`, `zaiToolStream`) | Direct port | Med | `agent/env.py`; include `CACHE_RETENTION` constants. |
| B10 | `tau_ai/http.py` | 81 | *(none — uses openai lib)* | 0 | 81 | `create_async_client(timeout=60)` factory | Direct port | Low | `agent/http.py` (httpx.AsyncClient with sane defaults). |
| B11 | `tau_ai/http_errors.py` | 65 | *(none)* | 0 | 65 | `provider_http_error_message()` mapping 4xx→user text | Direct port | Low | `agent/http_errors.py`. |
| B12 | `tau_ai/retry.py` | 62 | `agent/provider_retry.py` | 27 | 35 partial | `retry_delay_seconds`, `wait_for_retry` (jitter, max_delay, signal-aware) | Partial — lean uses `threading+time.sleep`; Tau uses async `anyio.wait_for_retry` with `CancellationToken`. | Low | Expand `agent/provider_retry.py` to async variant + Tau's provider-specific status codes (`_is_transient_status`). |
| B13 | `tau_ai/events.py` | 37 | *(none)* | 0 | 37 | `AssistantMessageEvent` hierarchy (`AssistantDoneEvent` etc) for `canonicalize_provider_stream` consumers | Direct port | Low | `agent/provider_events` supplement. |
| B14 | `tau_ai/model_limits.py` | 48 | `agent/model_limits.py` | 38 | 10 partial | `RuntimeModelLimits`, `ModelLimitsProvider` discovery (live catalog fetch) | Partial — lean stores static `_DEFAULT_CONTEXT_WINDOW_TOKENS`; Tau discovers live limits per provider/model via API. | Med | Port `ProviderModelLimits` fetch + cache; integrate into `agent/llm.py context_window_tokens()` fallback chain: `override > profile > live limits > static prefix`. |
| B15 | `tau_ai/fake.py` | 41 | *(none)* | 0 | 41 | `FakeProvider` for tests | Direct port | Low | `agent/providers/fake.py` for determinism. |
| B16 | `tau_ai/tool_call_ids.py` | 24 | *(none)* | 0 | 24 | `portable_tool_call_id()` sanitization | Direct port | Low | `agent/tool_call_ids.py`. |
| B17 | `tau_ai/openai_cache.py` | 20 | *(none)* | 0 | 20 | `is_direct_openai_url`, `openai_prompt_cache_key` | Direct port | Low | `agent/openai_cache.py`. |

### 2C. `src/tau_coding` — Coding Session + Host (20 418 LOC total)

| # | Tau file | LOC | lean file | lean LOC | Gap | Purpose | Lean Adaptation | Cplx | Steps |
|---|----------|-----|-----------|----------|-----|---------|-----------------|------|-------|
| C1 | `tau_coding/session.py` | 3389 | `agent/session.py`+`loop.py` | 94+734 | **~3200** | `CodingSession` ( `load()` → durable `SessionState`, `run_agent_loop`, `manage CodingSessionConfig`, skills/templates/context, compaction, branching, extensions binding, trust) | **Core rewrite**. Lean uses flat `prove()` + `history:list[dict]`. Must port `CodingSession` façade that lean's TUI/`prove()` can be adapted to call. | High | 1. Create `agent/coding_session.py` (or `agent/session/coding.py`) porting `CodingSession`, `CodingSessionConfig`, `ModelChoice`, `CompactionPlan`, `_PendingMessageWrite`. 2. Stage `resource_paths_with_project_trust`. 3. Keep lean `prove()` as `prove_with_coding_session()` adapter initially. |
| C2 | `tau_coding/tools.py` | 1215 | `agent/tools.py` | 77 | **1138** | `read`/`write`/`edit`/`bash` with `ImageSupportState`, truncation (head vs tail), per-path locks, `detect_line_ending`, `generate_unified_patch`, process-group kill | **Full port + Lean fork**: `bash` stays, `read` must handle `Prover.lean`/`ProverSupport` paths; image branch maps to Lean shim (no vision model yet, return omitted note). | High | 1. Port `ToolDefinition` + 4 factories verbatim. 2. Add `agent/image_processing.py` shim (see C3). 3. Port `_kill_process_tree` POSIX + Windows. 4. Add per-path `asyncio.Lock` registry. 5. Wire `ImageSupportState.supported` via `agent/llm.supports_images`. |
| C3 | `tau_coding/image_processing.py` | 253 | *(none)* | 0 | 253 | Bounded image normalization (Pillow, BMP/PNG/JPEG/WebP, 5 MiB inline / 50 MiB source / 40M px, LANCZOS resize loop) | **Lean shim**: Lean proofs don't attach images; but TUI paste/path drop may. Full port with Pillow opt-in (`try import PIL`). When missing, return `ImageProcessingFailure("Pillow not installed")`; tests skip. | Med | Create `agent/image_processing.py` port verbatim (keep `PngKind` classifier, `DEFAULT_MAX_*` constants). Guard import. |
| C4 | `tau_coding/provider_config.py` | 2563 | `agent/providers.py` 19 + `catalog.py` 16 | ~2528 | Tied for largest file — durable `ProviderConfig` variants (`OpenAICompatible`/`Anthropic`/`OpenAICodex`), `ProviderSettings` JSON, `scoped_models`, `inference_providers`, `thinking_defaults`, catalog merge, atomic writes + `.bak`, legacy migration | **Full port** — lean `models.py` (160 LOC) stores only `ModelProfile(name,label,base_url,api_key,context_window,cost)`. Must replace/extend. | High | 1. Create `agent/provider_config.py` porting all `ProviderConfig` dataclasses + `provider_settings_from_json` + `save_provider_settings` (atomic + backup). 2. Migrate lean `~/.prover/models.json` → `~/.prover/providers.json` (keep read compat). 3. Port `_effective_provider_configs` + `_append_catalog_providers` using `FileCredentialStore`. |
| C5 | `tau_coding/catalog_loader.py` | 681 | *(none)* | 0 | 681 | `builtin_catalog()`, `effective_catalog()` (builtin + `catalog.toml` overlay), `save_user_catalog_entries`, `provider_config_from_catalog_entry` | Full port | Med | `agent/catalog_loader.py` + point `provider_catalog.py BUILTIN_PROVIDER_CATALOG` at it. |
| C6 | `tau_coding/provider_catalog.py` | 111 | `agent/catalog.py` | 16 | 95 | `ProviderCatalogEntry`, `ModelCatalogMetadata`, `ModelCostTier`, `BUILTIN_PROVIDER_CATALOG` | Partial — lean `PROVIDER_CATALOG` dict is 5 entries; Tau is 10+ with `model_metadata`, `thinking_level_map`, `cost_tiers`, `context_windows`. | Med | Extend `agent/catalog.py` to re-export Tau's typed entries; keep lean dict as legacy. |
| C7 | `tau_coding/provider_runtime.py` | 349 | *(none — in llm.py `client()`)* | 0 | 349 | `create_model_provider(config, credential_store)` → `ClosableModelProvider`, `HuggingFace` pinning `response_headers_observer` | Direct port | Med | `agent/provider_runtime.py`; enable OAuth `credential_resolver` seam (`OAuthRuntimeAuth`). |
| C8 | `tau_coding/credentials.py` | 241 | *(none — ad-hoc env read)* | 0 | 241 | `FileCredentialStore`, `OAuthCredential`, `credentials_path()` (`~/.tau/credentials`) | Full port | Med | `agent/credentials.py`; use `~/.prover/credentials` path. |
| C9 | `tau_coding/session_export.py` | 1689 | `agent/session_export.py` | 130 | 1559 | `export_session_artifact()` → HTML/JSON/markdown export with transcript + tool results + skills panel | Partial — lean renders ~130 LOC HTML; Tau builds full artifact with `ProjectContextFile` + `Skill` sections, truncation previews, cost table. | High | Extend `agent/session_export.py` with `normalize_export_format`, `default_session_export_artifact_path`, `BranchSummary` rendering. |
| C10 | `tau_coding/session_manager.py` | 348 | `agent/session_manager.py` | 206 | 142 | `SessionManager` (indexed `~/.tau/sessions/index.json`, `list_sessions`, `touch_session`, `history_from_records`) | Partial — lean `SessionManager` exists but stores minimal fields (`SessionRecord` vs Tau `CodingSessionRecord` with `provider_name`/`inference_provider`/`title`). | Med | Extend `agent/session_manager.py` with `title`, `inference_provider`, `preserve_inference_provider`, `touch_session` semantics. |
| C11 | `tau_coding/session_stats.py` | 146 | `agent/session_stats.py` | 66 | 80 | `calculate_session_stats(entries)` with `cost_tiers`, `cacheRead/cacheWrite`, per-tier `model_cost_for_input_tokens` | Partial — lean computes simpler token counts; missing tiered cost. | Low | Add `cost_tiers` + `pricing_for_response` callback parity. |
| C12 | `tau_coding/session_usage.py` | 920 | `agent/session_usage.py` | 228 | 692 | `SessionUsageOverlay` (usage dashboard: per-provider billed tokens, context window gauge) | Partial — lean has basic aggregation; missing overlay + `provider_name` dimension. | Med | Extend `agent/session_usage.py` with overlay rendering used by `/usage` command. |
| C13 | `tau_coding/context.py` | 95 | `agent/context.py` | 8 | 87 | `discover_project_context_with_diagnostics()` — loads `AGENTS.md` (+ nested) + `DISCOVERY_FAILED` diagnostics | Partial — lean reads single `AGENTS.md` with no diagnostics. | Low | Port `ProjectContextFile` tuple + diagnostics seam. |
| C14 | `tau_coding/context_window.py` | 353 | `agent/context_window.py` | 99 | 254 | `ContextUsageEstimate`, `estimate_context_usage(system, messages, tools)` (tiktoken-ish), `auto_compaction_threshold_for_context_window`, `summarize_messages_for_compaction()` | Partial — lean `estimate_context_tokens()` counts raw chars; Tau tokenizes per-tool JSON. | Med | Port LLM-side estimators; keep lean `compaction.py` callsite but feed it Tau-shaped `ContextUsageEstimate`. |
| C15 | `tau_coding/diagnostics.py` | 163 | `agent/diagnostics.py` | 120 | 43 | `AgentCallDiagnosticLogger` → `logs_dir/*.jsonl` (run ID, model, cwd, session_id) | Partial — lean `ProofCallDiagnosticLogger` similar but keyed on proof calls; missing `AgentCallDiagnosticContext` fields. | Low | Extend `agent/diagnostics.py` with `from_paths(TauResourcePaths)` factory. |
| C16 | `tau_coding/resources.py` | 331 | *(none)* | 0 | 331 | `TauResourcePaths` (themes dirs, skills dirs, template dirs, trust filters), `discover_system_prompt_resources()` | Direct port | Med | `agent/resources.py` + `TauPaths` (see C17). |
| C17 | `tau_coding/paths.py` | 130 | `agent/paths.py` | 60 | 70 | `TauPaths(home, config_dir)` (XDG, `~/.tau`, `~/.config/tau`, sessions/logs) | Partial — lean `ProverPaths(config_dir ~/.prover)` single path. | Low | Extend `agent/paths.py` with `TauPaths` + `TauResourcePaths` factory; keep alias. |
| C18 | `tau_coding/project_trust.py` | 674 | `agent/project_trust.py` | 502 | 172 | `ProjectTrustCoordinator`, `ProjectTrustStore` (`~/.tau/trust.json`), `CanonicalProjectPath`, `TrustChoice`/`TrustOverride`, `format_trust_diagnostic` | Partial — lean `project_trust.py` ports ~502 LOC (good) but missing `ExtensionTrustResult` decider seam + `decide_project_trust` handler for extensions. | Med | Add `ExtensionTrustResult` + `ProjectTrustEvent` → `ExtensionRuntime.decide_project_trust` consult (Phase 15 dep). |
| C19 | `tau_coding/prompt_templates.py` | 217 | `agent/prompt_templates.py` | 222 | **~0 (done)** | `PromptTemplate`, `load_prompt_templates_with_diagnostics`, `expand_prompt_template_command` | **DONE** — lean 222 LOC already mirrors Tau (check `with_diagnostics` variant missing; trivial). | Low | Add `load_prompt_templates_with_diagnostics()` returning `ResourceDiagnostic` tuple. |
| C20 | `tau_coding/skills.py` | 255 | `agent/skills.py` | 23 | 232 | `Skill`, `load_skills_with_diagnostics`, `expand_skill_command`, `parse_skill_invocation` | STUB — lean `skills.py` returns empty list / no-op. | Med | Port `Skill` (name/path/description/disable_model_invocation), skill discovery over `TauResourcePaths`, `SKILL.md` frontmatter. |
| C21 | `tau_coding/system_prompt.py` | 210 | `agent/prompt_templates.py` (partial) | 0 | 210 | `build_system_prompt(BuildSystemPromptOptions{tools,skills,custom_prompt,append_system_prompt,context_files,extra_guidelines})` + `format_skills_for_prompt` | SKIPPED — lean prompt is hardcoded `SYSTEM` in `loop.py`. | Med | Create `agent/system_prompt.py` port; call sites update `loop.py`/`coding_session.py` to build system via builder not constant. |
| C22 | `tau_coding/thinking.py` | 90 | `agent/thinking.py` | 164 | **~parity** | `ThinkingLevel` (`off|minimal|low|medium|high|xhigh`), `thinking_level_from_env()`, `reasoning_effort_for_level`, `ThinkingParameter` | DONE-ish — lean actually **exceeds** Tau (164 vs 90, supports `Qwen`/`deepseek` mappings). Verify parity: add `thinking_level_map` from `ProviderModelMetadata`. | Low | Gap: per-model `thinking_level_map` override not wired. Patch lean `thinking.py` to consult `provider_config`'s map before global table. |
| C23 | `tau_coding/branch_summary.py` | 214 | `agent/branch_summary.py` | 157 | 57 | `summarize_branch_messages_with_model()` + `BRANCH_SUMMARY_PREAMBLE` | Partial — lean summarizes via `llm.chat`; missing `replace_instructions` flag + `custom_instructions` handling identical. | Low | Port `custom_instructions` + `replace_instructions` semantics; align preamble string. |
| C24 | `tau_coding/reload.py` | 31 | `agent/reload.py` | 87 | **lean larger** | `ReloadSnapshot`, `build_reload_summary`, `take_reload_snapshot` | DONE — lean 87 > Tau 31 (adds `ReloadCategorySummary`). Verify parity of `ReloadCategorySummary` field names. | Low |
| C25 | `tau_coding/shell_config.py` | 74 | *(none)* | 0 | 74 | `load_shell_settings()` (prefix, `bash` tool `shell_command_prefix`) | SKIPPED | Low | `agent/shell_config.py` + wire into `provider_config` → `create_coding_tools`. |
| C26 | `tau_coding/commands.py` | 876 | `agent/commands.py` | 538 | 338 | `create_default_command_registry()` with 22 commands (`/login`, `/logout`, `/model`, `/thinking`, `/compact`, `/tree`, `/fork`, `/export`, `/usage`, `/skills`, `/contexts`, `/tools`, `/branch`, `/new`, `/resume`, etc.) — `CommandResult` flags include `tree|fork|switch_session|set_model_choice|set_thinking` | Partial — lean 538 LOC has 24 commands but flags diverge: lean `CommandResult` missing `tree_picker_requested`, `fork_requested`, `set_model_choice`, `set_thinking` — has prover-specific `/prove`, `/run`, `/workers`, `/board` instead. | High | Merge registries: keep prover extras, add Tau parity flags; port Tau-specific handlers (`/login`, `/skill:`, `/tree`, `/fork`, `/export html`). Wire `/login` to `agent/oauth`. |
| C27 | `tau_coding/events.py` | 91 | `agent/events.py` | 66 | 25 | `CodingSessionEvent` union (`AgentSettledEvent`, `AutoRetryStart/End`, `CompactionStart/End`, `QueueUpdateEvent`, `SessionAgentEndEvent`) | Partial | Low | Add coding-specific events to `agent/events.py`; keep proof events. |
| C28 | `tau_coding/update_check.py` | 379 | *(none)* | 0 | 379 | `check_for_updates()` (PyPI polling, `releases.json`, `should_check`, throttle) | SKIPPED | Med | `agent/update_check.py` (Lean adaptation: poll `lean-prover` package, not `tau`). |
| C29 | `tau_coding/updater.py` | 387 | *(none)* | 0 | 387 | `install_update()`, `run_updater()` (uv/pipx) | SKIPPED | Med | `agent/updater.py` (same adaptation). |
| C30 | `tau_coding/version.py` | 16 | *(none — in __init__.py)* | 0 | 16 | `current_version()` | Low | `agent/version.py` (read from `pyproject.toml`). |
| C31 | `tau_coding/cli.py` | 1121 | `agent/main.py` | 563 | 558 | `tau` entry point (argparse, `provider_config` selection, `CodingSession.load`, `tui|print|rpc` dispatch, `PROVER_TRUST` etc) | Partial — lean `main.py` has prover-specific `prove <statement>`, `--full-file`, `--retrieval`, `benchmark` dispatch. Must merge: keep prover CLI, add Tau parity (`--session-id`, `rpc`, `login`, `--extensions`) without breaking prover. | High | Port `cli.py` dispatch table as `agent/cli.py` shim or extend `agent/main.py` with `CodingSession`-backed mode behind `prover --coding` flag; keep lean's single-problem loop fast. |
| C32 | `tau_coding/self_docs.py` | 23 | *(none)* | 0 | 23 | `/help` docs embed | Low | Inline into `agent/commands.py` help text. |
| C33 | `tau_coding/rendering/base.py` | 27 | `agent/rendering.py` (part) | 0 | 27 | `RenderOptions` | Direct port | Low |
| C34 | `tau_coding/rendering/json.py` | 24 | *(none)* | 0 | 24 | JSON transcript renderer | Low | `agent/rendering/json.py`. |
| C35 | `tau_coding/rendering/plain.py` | 34 | *(none)* | 0 | 34 | Plain text renderer | Low | `agent/rendering/plain.py`. |
| C36 | `tau_coding/rendering/transcript.py` | 97 | *(in tui.py+rendering.py)* | 0 | 97 | Transcript markdown renderer (Rich) | Low | `agent/rendering/transcript.py`. |
| C37 | `tau_coding/tui/config.py` | 207 | *(none — in tui.py+tui-adjacent)* | 0 | 207 | `TuiSettings`, `TuiKeybindings`, `TuiTheme`, `TAU_DARK_THEME`, `load_tui_settings` | Direct port (lean `tui.py` inline `TuiSettings` is subset). | Low | `agent/tui/config.py`. |

### 2D. `src/tau_coding/extensions` — Extensions (2 391 LOC)

| # | Tau file | LOC | lean | Gap | Purpose | Lean Adaptation | Cplx | Steps |
|---|----------|-----|------|-----|---------|-----------------|------|-------|
| E1 | `extensions/api.py` | 1001 | `agent/extensions.py` 24 | 977 | `ExtensionAPI`/`ExtensionContext`/`ExtensionUi`/`ComponentBridge`/`CustomMessageView`/`MainViewHandle`/`ExtensionGeneration` + event constants (`AGENT_EVENT_TYPES`, `LIFECYCLE_EVENT_TYPES`) + `NullUiBridge`/`StderrUiBridge` | Full port — lean stub has only `Extension(name,path,enabled)` + `discover_extensions()`. | High | Create `agent/extensions/` package; port `api.py` verbatim (keep Textual `Widget` TYPE_CHECKING guard). |
| E2 | `extensions/runtime.py` | 943 | *(none)* | 943 | `ExtensionRuntime` (dispatch, `compose_tools`+hook wrapping, `attach_harness_listener`, `emit_session_start`, `render_custom_message`, component seam `set_slot_widget`/`open_main_view`/`register_key_interceptor`) | Full port | High | `agent/extensions/runtime.py`. |
| E3 | `extensions/loader.py` | 350 | *(none)* | 350 | `load_extensions(paths, extra_paths)`, `unload_extension_modules()`, isolation + `setup(tau)` error capture | Full port | Med | `agent/extensions/loader.py` (importlib machinery, `sys.modules` cleanup). |

### 2E. `src/tau_coding/oauth*` — OAuth (1 388 LOC)

| # | Tau file | LOC | lean | Gap | Purpose | Lean Adaptation |
|---|----------|-----|------|-----|---------|-----------------|
| O1 | `oauth.py` | 527 | `agent/oauth.py` 14 | 513 | Codex PKCE `AuthorizationCode` flow (`create_pkce_pair`, `AuthorizationFlow`, `TokenResponse`, `_LocalOAuthServer`, `login_openai_codex`) | Full port — lean stub returns `None`. Lean-shim: full PKCE still works for lean users with ChatGPT Codex subscription. |
| O2 | `oauth_anthropic.py` | 285 | *(none)* | 285 | Anthropic OAuth (device-code variant) | Full port |
| O3 | `oauth_github_copilot.py` | 285 | *(none)* | 285 | Copilot device-code → `copilot_internal/v2/token` exchange | Full port |
| O4 | `oauth_device.py` | 109 | *(none)* | 109 | RFC 8628 `poll_oauth_device_code` helper | Full port |
| O5 | `oauth_registry.py` | 55 | *(none)* | 55 | `get_oauth_provider`, `register_oauth_provider` (3 built-ins) | Full port |
| O6 | `oauth_types.py` | 127 | *(none)* | 127 | `OAuthProvider` protocol, `OAuthLoginCallbacks`, `OAuthCredential` re-export, `OAuthPrompt` | Full port |

### 2F. `src/tau_coding/tui/*` — TUI (7 128+2604+918+… ≈ 11 000 LOC)

| # | Tau file | LOC | lean | Gap | Purpose | Lean Adaptation |
|---|----------|-----|------|-----|---------|-----------------|
| T1 | `tui/app.py` | 7128 | `agent/tui.py` 2055 | **5073** | Full Textual `TauTuiApp` (transcript `MarkdownStream`, prompt `TextArea`, sidebar, extension component seam, trust modal, `ProjectTrustScreen`, `CompletionState`, large-paste placeholder, file-drop Paste interception) | Partial — lean `ProverApp` is benchmark-focused (problem list, hammers). Must **merge**, not replace: keep prove-specific screens (`ProblemRow`, `Leaderboard`, `WorkersScreen`) and port Tau transcript richness. |
| T2 | `tui/widgets.py` | 2604 | *(in tui.py + tinkered rendering.py)* | ~2400 | `SessionSidebar`, `TranscriptView` (bounded DOM window `_WINDOW_ITEMS=200`, `MarkdownFence` theming, selection `get_selection`, `GroupedToolCall`, `BatchedTool` batching) | Port widget-by-widget; lean `SelectableRichLog` is simpler (no window, no grouping). |
| T3 | `tui/state.py` | 918 | `agent/compaction.py` + `session_usage.py` fragments | ~700 | `TuiState` ( `add_tool_call` batching, `record_tool_update`, `resolve_custom_markup`, `format_tool_call_invocation` ) | Partial — lean splits across `compaction.py`/`rendering.py`; Tau `TuiState` centralizes display batching. |
| T4 | `tui/adapter.py` | 154 | *(none)* | 154 | `TuiEventAdapter` (maps `AgentEvent` → `ChatItem` via `TuiState`) | Direct port |
| T5 | `tui/autocomplete.py` | 579 | `agent/autocomplete.py` 56 | 523 | `build_completion_state`, `CompletionItem`, `CompletionState`, slash-command + session-ID completion | Partial — lean 56 LOC is single `command_completions()` helper. |
| T6 | `tui/config.py` | 207 | *(embedded in tui.py:38)* | 207 | `TuiSettings.resolved_theme`, `TuiKeybindings`, `load_custom_tui_themes` | Extend lean inline `TuiSettings`. |
| T7 | `tui/file_drop.py` | 83 | `agent/file_drop.py` 73 | ~10 | `normalize_dropped_paths` (terminal drag-and-drop → normalized whitespace-separated paths) | **DONE** (73 vs 83, lean mirrors Tau). Add test for edge escapes. |
| T8 | `tui/project_trust.py` | 184 | *(in tui.py TrustScreen 100 LOC)* | ~84 | `ProjectTrustScreen` (choice list `trust-exact/trust-parent/trust-run/decline`) vs lean `TrustScreen` subset | Partial — lean `TrustScreen` trims protected input counts; port full `prompt_project_trust` flow. |
| T9 | `tui/terminal_notification.py` | 115 | `agent/terminal_notification.py` 116 | **0 done** | `TerminalNotificationController` (`auto|bell|off`, terminal bell) | **DONE** — lean 1:1 line parity. |
| T10 | `tui/terminal_title.py` | 124 | `agent/terminal_title.py` 94 | 30 | `TerminalTitleController` (OSC title updates) | Partial — lean 94 vs Tau 124; missing `update_from_state` throttling. |
| T11 | `tui/themes/__init__.py` | ~80 + JSON | `agent/themes.py` 196 | partial | `available_tui_theme_names`, `textual_theme_variables`, `theme_css_variables`, 3 JSON themes | Partial — lean `themes.py` ports core but missing `load_custom_tui_themes` from user themes dirs. |

### 2G. Misc — Rendering / Root `tau_coding`

Remaining smaller files skipped/partial: `rendering/*` (185 LOC total), `resources.py` 331, `catalog_loader.py` 681, `shell_config.py` 74, `update_check`/`updater` (~770), `rpc.py` 798 (re-uses done `mcp.py` 268 LOC stub), `cli.py` 1121, `version.py` etc — catalogued in §2C above. Total skipped group ~3 200 LOC.

**Grand gap summary:** ~32 200 LOC remaining to port (42 023 − 9 830) once divergent lean files are normalized. Largest single chunks: `tui/app.py` 7 128, `session.py` 3 389, `provider_config.py` 2 563, `extensions/api+runtime` 1 944, `session_export` 1 689.

---

## 3. Phase Overview & Dependency DAG

```
Phase 12: Agent Core ─┐
                     ├─► Phase 14: Coding Session ─┬─► Phase 15: Extensions+OAuth
Phase 13: Provider Fleet ─┘                         └─► Phase 16: TUI+CLI
                                                   Phase 13 must finish before
                                                   Phase 14 can build real providers
```

| Phase | Title | Tau scope | New LOC | Effort (eng-weeks) | Dependencies | Risk |
|-------|-------|-----------|---------|-------------------|--------------|------|
| **12** | Agent Core Hardening | `tau_agent/*` (15 files) | +1 600 | 2 | None (foundation) | **Med** — API surface migration; `prove()` backwards-compat risk. Mitigate: keep `prove` export, add `agent_compat` shim. |
| **13** | Provider Fleet & Transport | `tau_ai/*` (17 files) | +4 200 | 3 | Phase 12 (`provider.py`, `tool_history`) | **High** — async streaming + retry + image fallbacks are subtle. Mitigate: port `stream.py`'s `canonicalize_provider_stream` 1:1 with golden traces. |
| **14** | Coding Session Substrate | `session.py`, `tools.py`, `provider_config/catalog`, `resources/paths`, `credentials`, `trust(non-ext)`, `system_prompt/skills/context_window` | +6 800 | 4 | Phases 12,13 | **High** — largest impl; `CodingSession.load()` orchestrates storage, trust, extensions, provider, tools (order matters). Mitigate: port `session.py` tests first; stage behind flag. |
| **15** | Extensions + OAuth + RPC | `extensions/*`, `oauth*`, `rpc.py` + hooks into trust/commands/TUI | +4 500 | 3 | Phase 14 (needs bound session + trust event) | **High** — isolation (`sys.modules` unload), `ComponentBridge` Textual type dependency, OAuth device/brower flows. |
| **16** | TUI + Rendering + CLI | `tui/*`, `rendering/*`, `cli.py`, `update_check/updater`, `commands` merge, `session_export/manager/stats` expansions | +5 300 | 4 | Phases 14,15 | **Med-High** — 7k LOC app merge (prove list vs transcript). Mitigate: keep lean `ProverApp` subclass `TauTuiApp`; feature-flag the transcript widgets. |

**Total: ~+22 400 new LOC (net +32 k when divergent prover code counted), 16 eng-weeks, 5 sequential phases with 2 parallelizable tracks (13 & 12 can start together; 15 & tail of 16 can overlap).**

---

## 4. Phase 12 — Agent Core

**Goal:** Lean's proof loop sits *on top of* Tau's generic agent loop, not beside it.

**Files to create/modify:**

* New `agent/provider.py` (37 LOC) — `CancellationToken` + `ModelProvider` ABC.
* New `agent/tool_history.py` (169) — `repair_tool_history`.
* New `agent/session/` package — `entries.py` (117), `jsonl.py` (111), `storage.py` (42), `memory.py` (136), `tree.py` (40), `__init__.py` (50) — `SessionState`, `LeafEntry` etc.
* Modify `agent/loop.py` → extract prove-specific logic to `agent/prover_loop.py` (keep 734 LOC), rewrite `agent/loop.py` to Tau `run_agent_loop` (328).
* Modify `agent/tools.py` → port `ToolDefinition` + `prepare_arguments`/`execution_mode`/`render_call`/`render_result` + `AgentToolResult.added_tool_names` (118 vs 77).
* Modify `agent/messages.py` — typed `AgentMessage` union (278).
* Modify `agent/events.py` — add typed `AgentEvent` variants (keep lean `record()` API).
* Add `agent/types.py` (8).

**Key adapter:** `agent/prover_loop.py` implements `prove()` by calling `run_agent_loop` with a `lean_check_tool`/`lsp_goals_tool`/`retrieval_tool` tool set + Lean-specific system prompt constant (existing `HEADER/SYSTEM`). This validates that Tau's `repair_tool_history` correctly strips `error/aborted` empty assistant messages (Tau `loop.py:178 _provider_context`).

**Verification:** Port Tau `tests/tau_agent/` (loop turn sequencing, tool history repair, storage JSONL U+2028 test, harness `queued_messages` asserts).

**New LOC:** +1 600 (≈1 300 new files + ~300 edits to existing).

**Risk:** Mid — changing `messages` from `list[dict]` to `tuple[AgentMessage,...]` breaks `agent/retrieval.py` callers. Mitigate with `message_to_user()` compat helper (already exists in `tau_ai/content.py`).

---

## 5. Phase 13 — Provider Fleet

**Goal:** Lean can actually call every model Tau can.

**Files:** All `tau_ai/*.py` → `agent/providers/*` + shims.

**Priority order (dependencies first):**

1.  `tool_call_ids.py` (24), `openai_cache.py` (20), `http.py` (81), `http_errors.py` (65), `content.py` (45), `_provider_events.py` (93), `events.py` (37) — pure utils.
2.  `retry.py` (expand `agent/provider_retry.py` 27→62) — async `wait_for_retry(delay, signal)` with `asyncio.sleep` + jitter.
3.  `env.py` (157) — `OpenAICompatibleConfig` (fields: `base_url`, `api_key`, `headers`, `compat`, `reasoning_effort`, `supports_images`, `response_provider_header`, `credential_resolver`, `response_headers_observer`).
4.  `stream.py` (212) — `canonicalize_provider_stream` (must pass Tau's streaming golden files: reasoning → `ThinkingContent`, `tool_calls` → `ProviderToolCallEvent`).
5.  `openai_compatible.py` (1364) — largest; includes `_ChatStreamParser`, `_ResponsesStreamParser`, `_build_chat_payload`, `_build_responses_payload`, session affinity header injection. **Decision:** Implement as `agent/providers/openai_compatible.py` using `httpx.AsyncClient` + `client.stream(POST ...)`. Keep lean's sync `llm.chat()` as thin `asyncio.run(stream_response(...))` wrapper during migration.
6.  `openai_codex.py` (1080), `anthropic.py` (771), `google.py` (493), `mistral.py` (525) — follow same `_stream` envelope; point Tau `openai_codex.DEFAULT_OPENAI_CODEX_BASE_URL` via `agent/credentials.py`.
7.  `provider.py` (5) — re-export.
8.  `fake.py` (41) + `model_limits.py` (48) — live limits fetch (`GET /models` or `models.list()`).

**Lean adaptations:**

*   Lean provas default to `qwen/qwen3-8b` local endpoint (`OPENAI_BASE_URL`). Tau's `OpenAICompatibleConfig.thinking_format` already handles `qwen` (`chat_template_kwargs.enable_thinking`) — keep lean's `thinking.py` wiring.
*   `llm.py` `HARD_TIMEOUT=600` thread-join wall-clock cap becomes `CancellationToken` timeout passed to `stream_response`; keep thread shim for non-async callers.
*   Image routing: `detect_supported_image_mime_type` gates vision requests; `tool_result` pending images get a follow-up user message (see `openai_compatible._openai_tool_image_message`).

**Verification:** Record/replay streaming fixtures for chat vs responses endpoints; assert Tau's `_usage_from_responses_event` vs `context_window` integration passes. Run lean's benchmark dry-run (no API key) through `FakeProvider`.

**New LOC:** +4 200.

**Risk:** High — the two parsers are the most defect-prone (one off-by-one in `thinking_signature` breaks checkpoint caching). Mitigate: copy Tau parser classes verbatim (including variable names) and add property-based SSE fuzz.

---

## 6. Phase 14 — Coding Session Substrate

**Goal:** `await CodingSession.load(config)` replays durable `SessionState`, resolves trust, discovers skills/templates, composes tools, and binds `AgentHarness` — same ordering as Tau `session.py:362 load()`.

**Files (new LOC largest phase):**

* `agent/coding_session.py` (→ `agent/session/coding.py`) **3389** LOC port — dataclasses `CodingSessionConfig(18 fields incl. `resource_paths: TauResourcePaths`, `trust_override`, `extension_paths`)` + all methods (`set_model`, `set_thinking_level`, `branch_to_entry`, `queue_steering_message`, `append_custom_entry`, `emit_pending_session_start`, context-usage cache). Must replicate **load ordering**: `read_all → _detach_missing_parents → SessionState.from_entries(leaf_id) → resolve trust → discover resources → create_coding_tools(image_support) → extension_runtime.compose_tools → build_system_prompt → AgentHarness(...) → bind & attach_harness_listener`. Miss one step → `/reload` breaks.
* `agent/tools/coding_tools.py` (1215) — `create_read_tool_definition` (image branch: `DEFAULT_MAX_SOURCE_IMAGE_BYTES` check + `process_image` + `ImageSupportState.supported==False` omitted note), `truncate_head/tail` (lines vs bytes), `format_size`, `apply_edits_to_normalized_content` (non-overlapping + duplicate exact-match checks), `generate_unified_patch`, `_file_lock` per-path `asyncio.Lock`.
* `agent/image_processing.py` (253) — Pillow-guarded shim (see §9).
* `agent/provider_config.py` (2563), `agent/provider_catalog.py` (111), `agent/catalog_loader.py` (681), `agent/provider_runtime.py` (349) — see inventory rows C4-C7. `provider_config` atomic writes use `NamedTemporaryFile` + `Path.replace`; lean must retain `~/.prover/models.json` read-compat for existing users.
* `agent/credentials.py` (241), `agent/resources.py` (331), `agent/paths.py` (extend 60→130), `agent/shell_config.py` (74).
* `agent/system_prompt.py` (210), `agent/skills.py` (255→ extend stub), `agent/context.py` (extend 8→95), `agent/context_window.py` (extend 99→353), `agent/diagnostics.py` (extend).
* `agent/branch_summary.py` (57 gap), `agent/reload.py` (0), `agent/session_export.py` (+1559), `agent/session_manager.py` (+142), `agent/session_stats.py` (+80), `agent/session_usage.py` (+692).

**Lean adaptations:**

* `cwd` default becomes `lean-prover` repo root; `AGENTS.md` already exists in `lean-prover/agent` context. Add Lean-specific project context file `.prover.md` alongside `AGENTS.md` (discovery scans both).
* `create_coding_tools(cwd)` lean fork: `read` offset/limit semantics already used by `agent/tools.py` lean_check; keep identical truncation constants (`50*1024` bytes, `2000` lines) so LLM prompts match.
* `provider_catalog` Lean extension: add `lean-prover` provider entry `qwen-local` as builtin with `thinking_default: off` (mirrors lean's PROVER_THINKING default).
* `session_export` HTML titles: `_session_export_title` uses `ModelChoice` → lean session titles.

**Dependencies:** Phase 12 (`SessionState`, `ToolHistoryRepair`), Phase 13 (`create_model_provider`, `credential_resolver`).

**Verification:** End-to-end `CodingSession.load` test that writes `MessageEntry`→`LeafEntry` via `JsonlSessionStorage`, reloads, asserts `harness.messages` round-trips; trust-store tmpdir test.

**New LOC:** +6 800.

**Risk:** High — ordering & missing `pending_initial_entries` (Tau `session.py:379`). Mitigate: diff Tau `load()` line-by-line during review.

**✅ DONE (lean-adapted, 2026-08-20):** Phase 14 shipped lean-adapted (Tau session.py 3389 + provider_config 2563 + tools 1215 → ~1.3k LOC). `CodingSession.load()` replicates Tau ordering (provider resolution → resource/context discovery → tool composition → system prompt build → `AgentHarness` bind). `agent/session/` package: entries/jsonl/storage/memory/tree + legacy flat JSONL moved to `session/flat.py`. `agent/coding_tools.py`: read/edit/write/bash with CRLF round-trip, exact-match edits, unified patches, per-path locks. `provider_config.py` atomic save+`.bak` + legacy `models.json` migration. `catalog_loader.py` builtin catalog (qwen-local, openai, anthropic, deepseek, mistral). Extensions: `system_prompt.py`, `skills.py`, `context.py`, `context_window.py` (typed messages), `paths.py` (TauPaths), `resources.py` (TauResourcePaths), `shell_config.py`, `image_processing.py` (Pillow-guarded shim), `ToolResult.added_tool_names`. 458 tests green (20 new in `test_coding_session.py`), `ruff` clean, prover CLI intact.

---

## 7. Phase 15 — Extensions + OAuth + RPC

**Goal:** Lean-prover can load Python extensions, enforce Budou-style trust, and serve Pi-compatible JSONL RPC.

#### 7A. Extensions (2 391 LOC)

* `agent/extensions/__init__.py` (97) + `agent/extensions/api.py` (1001) — `ExtensionAPI(Context, Ui, Components)`, `CustomMessageView`, `MessageRenderer`, `ToolCallMarkup`, `MainViewHandle`/`MainViewFactory`, `ExtensionGeneration` stale guard (`assert_active()` on every property), `UiBridge` (`has_ui`, `select/confirm/input`, `Theme`, `get_prompt_text`, `set_slot_widget`, `open_main_view`, `register_key_interceptor`, `clear_components`), `NullUiBridge`/`StderrUiBridge`.
* `agent/extensions/runtime.py` (943) — `ExtensionRuntime` (`load(paths, extra_paths)`, `compose_tools(builtin_tools) → wrap with hook seams`, `decide_project_trust(event)`, `run_input_hooks(text) → InputHookOutcome(handled|transform)`, `emit_event(agent_event)`, `_on_agent_event (TurnStart/End adapt)`, `build_command_registry`, `render_custom_message` with `renderer_failures_reported` dedupe, `reset_for_reload` invalidating generation + `unload_extension_modules`, `retire` stale generation).
* `agent/extensions/loader.py` (350) — `load_extensions()` scanning `TauResourcePaths` (`extensions_dirs`, `extra_paths`), `LoadedExtension(name, path, setup)`, `unload_extension_modules()` (`sys.modules` purge of `tau_*` prefix). **Lean path:** scan `ProverPaths().config_dir / "extensions"` + `data/examples/extensions` overlay; keep `.py` glob parity with current `discover_extensions`.

**Textual seam decision (keep):** `ComponentBridge` exposes `Widget` (Textual) under `TYPE_CHECKING` — same contract as Tau: Textual is in the extension ABI; a major bump is coordinated. Print-mode extensions use `NullUiBridge` (never import Textual).

#### 7B. OAuth (1 388 LOC)

* `agent/oauth/token.py` (527 → `agent/oauth.py` expanded), `agent/oauth/anthropic.py` (285), `agent/oauth/github_copilot.py` (285), `agent/oauth/device.py` (109), `agent/oauth/registry.py` (55), `agent/oauth/types.py` (127) — exact Tau port.
* Includes: `create_pkce_pair → verifier+challenge`, `AuthorizationFlow(url)`, `AuthorizationCode`, `TokenResponse`, `_LocalOAuthServer(ThreadingHTTPServer)` on `127.0.0.1:1455`, `account_id_from_access_token` JWT decode (`https://api.openai.com/auth` claim), `oauth_credential_is_expired(skew 60s)`.
* **Lean shim:** lean-prover defaults to API keys; OAuth flows are available via `prover login openai-codex|anthropic|github-copilot`. `agent/credentials.py OAuthCredential` stores `access/refresh/expires/account_id/metadata.enterprise_domain`. Lean `llm.client()` gets `credential_resolver` that refreshes when `oauth_credential_is_expired`.

#### 7C. RPC (798 LOC)

* `agent/rpc.py` (7→798) — `RpcServer(session: RpcSession, stdin, stdout)` + `run_rpc_session(session)`.
* Must support all command types: `prompt|steer|follow_up` (+ `streamingBehavior` snake/camel alias), `abort`, `get_state` (returns `model wire` via `_model_wire(provider.model_metadata)` incl. `input: ["text","image"]`), `get_messages`, `get_available_models`, `set_model`, `cycle_model`, `cycle_thinking_level`, `get_available_thinking_levels`, `set_thinking_level`, `compact`, `set_auto_compaction`, `bash`/`abort_bash`, `new_session`, `switch_session`, `get_session_stats`, `export_html`, `get_fork_messages`, `get_entries(since cursor)`, `get_tree`, `get_last_assistant_text`, `set_session_name`, `fork`, `get_commands`. Lean `agent/mcp.py` (268) already implements `serve()` — RPC must reuse same `RpcSession` protocol, not duplicate.
* Wire `CodingSession` protocol (`prompt()` async iterator `CodingSessionEvent`, `cancel()`, `compact_detailed()`, `branch_to_entry()`, `run_terminal_command(add_to_context)`).

**Dependencies:** Phase 14 (`CodingSession` + `ProjectTrustEvent` → `extension.decide_project_trust`).

**New LOC:** +4 500 (extensions 2 391 + oauth 1 388 + rpc 798 + registry glue).

**Risk:** High — `ExtensionGeneration` staleness (security boundary), `ComponentBridge` main-view `async wait()` future race (close(c) while superseded). Mitigate: port Tau `tests/extensions/generation_test.py` exact semantics.

---

## 8. Phase 16 — TUI + Rendering + CLI + Misc

**Goal:** lean-prover TUI matches Tau `TauTuiApp` fidelity while preserving lean-prover benchmark panes.

**Files:**

* `agent/tui/app.py` (7128→ lean 2055): Port `PromptInput` (multiline `TextArea`, `PASTE_DISPLAY_THRESHOLD=2000` large-paste placeholder `[Pasted content #n: …]`, `handle_pasted_text → normalize_dropped_paths`, shell-mode `get_line` style, completion footer modes), `_TuiExtensionUiBridge` (dialog `ExtensionSelect/Confirm/InputScreen` class family, `set_slot_widget`, `open_main_view` with `call_after_refresh_anchor`, `register_key_interceptor` pre-dispatch in `on_event` before priority bindings), `Extension*Screen`, `ToolsReferenceScreen`, `PromptTemplatePickerScreen`, `PromptTemplateEditorScreen`, `SessionPickerScreen`, `CompletionActionTarget`, full `TauTuiApp` compose (`Header`, `TranscriptView`, `SessionSidebar`/`CompactSessionInfo`, `PromptInput`, `PaneDivider` etc). **Lean merge strategy:** Make `ProverApp(TauTuiApp)` subclass — keep `MAX_WORKERS`, `ProblemRow`, `LeaderboardScreen`, `ProveScreen`/`WorkersScreen`, add Tau transcript tab. Fugure `TabbedContent(Log, Goals, Errors, Proof)` → map to Tau `TranscriptView` with `ChatItem(role=tool|assistant|thinking|custom)` plus dedicated `Goals/Errors` side panels as `TabPane` within `TranscriptView` slot.
* `agent/tui/widgets.py` (2604): `SessionSidebar` (fingerprint `_session_summary_fingerprint(theme, cwd, provider, model, thinking_level, context_token, extensions…)`), `CompactSessionInfo`, `ThemedMarkdownWidget`/`TauMarkdownBlock` (`link-style-hover`, `MarkdownFence` background, selectable `allow_select` guard), `TranscriptWindowBoundary` (`Scroll for n earlier/later`), `TranscriptMessageWidget`/`StreamingTranscriptMessageWidget` (selection `extract_text_selection`, `refresh_invocation` no-flicker spinner, `get_stream().write(fragment)` streaming), `TranscriptView` bounded DOM (`TRANSCRIPT_WINDOW_ITEMS=200`, `PAGE=80`, `OVERSCAN=40`, follow_output `watch_scroll_y`, `_schedule_window_shift`).
* `agent/tui/state.py` (918): `TuiState.add_tool_call` batching (`BATCHABLE_TOOL_NAMES`, `GROUPABLE_FILE_TOOL_NAMES=file_tools`, `GroupedToolCall`), `record_tool_update`/`record_tool_result` with `format_tool_result_block` previews (`TOOL_RESULT_PREVIEW_LINES=8`, `TOOL_PATCH_PREVIEW_LINES=32`), `resolve_tool_invocation` via `tool_call_renderer`, `add_user_message` compaction summary parsing (`Branch summary (Ctrl+O)`, `Previous conversation summary:`), `load_messages` (projects `BranchSummaryMessage`/`CompactionSummaryMessage` into display), `format_tool_call_invocation` (`read path:offset-limit`, `bash` compact `→ Running …`/expanded `$ cmd`).
* `agent/tui/adapter.py` (154): `TuiEventAdapter` (agent `AgentEvent` → `state.add_item` / `add_tool_call`).
* `agent/tui/autocomplete.py` (579→56): `build_completion_state(registry, records)`, `CompletionState.items`, `CompletionOption`, slash-command fuzzy search + session-ID completions.
* `agent/tui/config.py` (207): `TuiSettings.resolved_theme`, `TuiKeybindings(queue_follow_up, accept_completion, ...)` with `Primary binding` mapping, `load_custom_tui_themes`, `save_tui_settings`.
* `agent/tui/file_drop.py` (83): Already at 73 LOC — gap ~10 (edge: escaped Windows paths). Add tests.
* `agent/tui/project_trust.py` (184) + `agent/tui/terminal_*` (124,115): Extend lean stubs.
* `agent/rendering/*` (185 total): `RenderOptions`, `render_json/plain/transcript` (lean `agent/rendering.py` 158 LOC covers subset).
* `agent/commands.py` merge (538→876): Add `CommandResult` flags `tree_picker_requested`, `fork_requested`, `set_model_choice`, `set_thinking_level`, `switch_session` + handlers `/_login_command`, `_tools_command` (`ToolReferenceScreen`), `_contexts`, etc. Keep lean `/prove|run|workers|board` extensions.
* `agent/main.py` vs `cli.py` (563 vs 1121): Merge entrypoints — keep lean `prover tui|prove|benchmark|leaderboard` subcommands; add Tau parity `prover --session-id`, `prover login`, `prover rpc`, `prover setup`, `PROVER_TRUST` env. Either split `agent/cli.py` new file (preferred) and make `main.py` re-export.
* Remaining: `agent/update_check.py` (379), `agent/updater.py` (387), `agent/version.py` (16), `agent/self_docs.py` (23), `agent/paths.py` expansion (70 gap), `agent/shell_config.py` (74).

**Lean adaptations:**

* Themes: lean `agent/themes.py` 196 LOC already mirrors Tau `themes/__init__.py`; add `load_custom_tui_themes(dir)` reading `*.json` from `themes_dirs` (resources-approved dirs only).
* Keybindings: lean `tui.py` re-binds single letters (`p`, `c`, `r` …) with no priority; Tau binds via `TuiKeybindings` (`ctrl+enter` submit, `shift+enter` newline). Keep lean vim nav (`j/k`, `space queue`) as additive.
* Pane width `PaneDivider` draggable — lean already has it (46 default, 20–400 range). Port Tau `sidebar` min `96` width guard.

**Dependencies:** Phases 14 (needs `CodingSession` for `update_from_session`, `model`/`provider_name`/`tools`), 15 (needs `ExtensionRuntime` UI bridge + `FileCredentialStore` for `/login`).

**New LOC:** +5 300.

**Risk:** Med-High — merging two TUI philosophies (benchmark dashboard vs transcript). Mitigate: snapshot tests of `TranscriptView.lines` (identity-based `_identity_index` fast path) and manual QA of `scroll_y` watch.

**✅ DONE (lean-adapted, 2026-08-20):** Phase 16 shipped lean-adapted. *Rendering:* `agent/rendering/` package (base `RenderOptions`, `events` legacy event renderers, `json`/`plain`/`transcript` conversation renderers over typed messages). *TUI substrate:* `agent/tui_state.py` (ToolCallDisplay, BatchedGroup, batch lines, result previews, custom-markup failure dedupe) + `agent/tui_adapter.py` (AgentEvent→ChatItem mapping). *Settings:* `TuiSettings` extended (large_paste_threshold, terminal_bell, window_title_updates) + `TuiKeybindings` + `resolved_theme`. *Autocomplete:* `CompletionState`/`CompletionItem` + `build_completion_state` (slash + session-id completions). *Commands:* `CommandResult` Tau flags (tree/fork/switch/set_model_choice/set_thinking/login/logout/skills/contexts/tools/update) + 9 new commands (`/tree /fork /login /logout /skills /contexts /tools /stats /update`), `/model m@p` provider parsing — registry 24→33. *Export:* markdown transcript + cost table (`/export`, `render_session_markdown`). *CLI:* `agent/cli.py` coding facade (`chat/version/update/login/export/rpc`). *Misc:* `version.py` (pyproject source), `self_docs.py`, `update_check.py` (PyPI poll + throttle), `updater.py` (uv>pipx>pip). 483 tests green (25 new in `test_phase16.py`), ruff clean.

---

## 9. Lean-Incompatible Features — Port vs Shim

| Feature | Tau behavior | Lean adaptation | Rationale | Risk |
|---------|--------------|-----------------|-----------|------|
| `image_processing` (Pillow) | Validates/resizes `jpg|png|gif|webp|bmp`, 5 MiB inline, converts BMP→PNG, rejects JXL/APNG | **Conditional full port**: gate on `try import PIL`; lean `read` tool detects images, when PIL missing returns `ImageProcessingFailure("Pillow not installed — install pillow")` and shows `[Image omitted]`. When vision model requested (`supports_images` true) but offline, same omit note — identical to Tau `ImageSupportState.supported==False` path. | Lean proofs are text-only today, but paste-of-screenshot bug reports are real. Pillow is heavy/mandatory for vision-capable hosts but optional for CI. | Low |
| `oauth device flow` (`oauth_device`, `github_copilot`) + `oauth` browser PKCE | Browser opens `auth.openai.com` / device code polling for Copilot / Anthropic | **Full port** — lean users with Copilot/Key subscriptions benefit directly; device flow works headless (polls `login/device/code`). No Lean conflict. Fallback: API-key path still canonical. `TAU_OAUTH_CALLBACK_HOST` → `PROVER_OAUTH_CALLBACK_HOST`. | No incompatibility, just additive. Tests mock `httpx.AsyncClient`. | Low |
| `shell_tools` (`bash` tool) | Runs arbitrary shell via `asyncio.create_subprocess_shell`, prefix `shell_command_prefix`, process-group `killpg`, tail truncation 50 KiB / 2000 lines, tmpfile full output | **Full port**: keep lean `lean_check_tool` separate; `bash` stays general-purpose but Lean-variant adds safety: block destructive `rm -rf lean/`? No — keep Tau parity (only path validation on `read`/`write`/`edit` locks, not bash). Add docs that Lean's `session.cwd` bounds tool roots. | Lean users already run `lake build`; proving without shell access is limiting. | Med |
| `extensions` Python `setup(tau)` | Isolation via `importlib`, `sys.modules` purge, generation staleness, TUI `Widget` hosting | **Full port** — lean extension ABI is narrower (no vision, Lean-specific tools). Document Textual version pin (`textual>=0.70,<1`). In headless `prover prove` mode, `NullUiBridge` (no widgets) still runs tool/command hooks. | Extension ABI break on Textual major bump is coordinated per Tau design. Lean inherits that. | Med |
| `provider_catalog` / `data/catalog.toml` | 10+ providers, per-model `cost_tiers`, `thinking_level_map`, `input: ["text","image"]` | **Full port**: lean `data/catalog.toml` gains same schema; `provider_catalog.py BUILTIN_PROVIDER_CATALOG=builtin_catalog()` identical. Add Lean-specific entry `qwen-local` (keep lean `OPENAI_BASE_URL` workflow). | No conflict. | Low |
| `project_trust` | Trust db `trust.json` gates loading of skills/exts/themes by `cwd`; extensions can `decide_project_trust` | **Full port**: lean stores trust at `ProverPaths().trust_path` (`~/.prover/trust.json`). Lean project context files (`AGENTS.md` + `.prover.md`) are also gated. Keep `PROVER_TRUST=always|ask|never` env. | Lean repo shares one `cwd` — trust still relevant for 3rd-party extensions. | Low |
| `tui` Textual Markdown streaming | `MarkdownStream` streaming fence chrome (`-streaming` vs `-finalized`), `MarkdownFence:light` selector bug fix | **Full port** — lean `ProverApp` already Textual. Keep benchmark pane; add transcript pane behind flag `--transcript`. | No Lean conflict. | Low |
| `rpc` Pi-compatible JSONL | `SESSION_DATA_DIR` sessions, `get_tree` leafId, `get_entries since` cursor, Pi aliases `followUp/streamingBehavior` | **Lean shim + full port**: lean-prover already serves `mcp`; RPC adds second entrypoint `prover rpc`. Lean's simpler `Session` (flat JSONL events) gets mapped through `SessionState` tree for `get_entries` wire. Add `_jsonable` handling for Pydantic `model_dump`. | RPC consumers expect `provider/modelMetadata.cost` fields — map lean `ModelProfile.cost_in/cost_out`. | Med |

---

## 10. File-by-File Mapping (Tau → lean-prover, new LOC)

> “New LOC” = lines to add/modify for full fidelity (includes replacements for stubs). `+X` means additive; `~X` means file is divergent/replace-in-place.

| Tau file | lean-prover destination | New LOC | Action |
|----------|-------------------------|---------|--------|
| `tau_agent/loop.py` 328 | `agent/loop.py` (rewrite) + `agent/prover_loop.py` (keep lean 734 as-is) | +340 (rewrite) | New `run_agent_loop` + move `prove()` to `prover_loop.py`. |
| `tau_agent/harness.py` 259 | `agent/harness.py` (replace stub 15) | +260 | Full port of `AgentHarness`. |
| `tau_agent/messages.py` 278 | `agent/messages.py` (replace stub 9) | +280 | Typed `AgentMessage` union. |
| `tau_agent/provider.py` 37 | `agent/provider.py` (new) | +40 | `CancellationToken` + `ModelProvider` protocol. |
| `tau_agent/provider_events.py` 107 | `agent/provider_events.py` (new) | +110 | Provider→agent typed events. |
| `tau_agent/events.py` 87 | `agent/events.py` (extend 66→~150) | +85 | Merge `AgentEvent` variants into existing `record()`. |
| `tau_agent/tools.py` 118 | `agent/tools.py` (extend 77→~200) | +125 | Add `ToolDefinition`, render hooks. |
| `tau_agent/tool_history.py` 169 | `agent/tool_history.py` (new) | +170 | `repair_tool_history`. |
| `tau_agent/types.py` 8 | `agent/types.py` (new) | +10 | `JSONValue` alias. |
| `tau_agent/session/__init__.py` 50 | `agent/session/__init__.py` (new package) | +50 | Re-exports. |
| `tau_agent/session/entries.py` 117 | `agent/session/entries.py` (new) | +120 | All `SessionEntry` subtypes. |
| `tau_agent/session/jsonl.py` 111 | `agent/session/jsonl.py` (new) | +110 | JSONL codec (U+2028-safe). |
| `tau_agent/session/memory.py` 136 | `agent/session/memory.py` (new) | +135 | In-memory storage for tests. |
| `tau_agent/session/storage.py` 42 | `agent/session/storage.py` (new) | +45 | `SessionStorage` + `JsonlSessionStorage` async. |
| `tau_agent/session/tree.py` 40 | `agent/session/tree.py` (new) | +40 | Leaf-entry helpers. |
| `tau_ai/openai_compatible.py` 1364 | `agent/providers/openai_compatible.py` (new) | +1350 | Largest provider (chat+responses). |
| `tau_ai/openai_codex.py` 1080 | `agent/providers/openai_codex.py` (new) | +1080 | Codex responses + OAuth base_url. |
| `tau_ai/anthropic.py` 771 | `agent/providers/anthropic.py` (new) | +770 | Claude Messages. |
| `tau_ai/google.py` 493 | `agent/providers/google.py` (new) | +490 | Gemini. |
| `tau_ai/mistral.py` 525 | `agent/providers/mistral.py` (new) | +525 | Mistral. |
| `tau_ai/stream.py` 212 | `agent/stream.py` (new) | +210 | `canonicalize_provider_stream`. |
| `tau_ai/_provider_events.py` 93 | `agent/provider_events.py` (merge above) | +(counted) | `ProviderEvent` set. |
| `tau_ai/content.py` 45 | `agent/content.py` (new) | +45 | Image-aware `text_and_images`. |
| `tau_ai/env.py` 157 | `agent/env.py` (new) | +160 | `OpenAICompatibleConfig`. |
| `tau_ai/http.py` 81 | `agent/http.py` (new) | +80 | `create_async_client`. |
| `tau_ai/http_errors.py` 65 | `agent/http_errors.py` (new) | +65 | User-facing 4xx mapper. |
| `tau_ai/retry.py` 62 | `agent/provider_retry.py` (extend 27→62) | +40 | Async `wait_for_retry`. |
| `tau_ai/events.py` 37 | `agent/provider_events.py` (merge) | +35 | `AssistantMessageEvent`. |
| `tau_ai/model_limits.py` 48 | `agent/model_limits.py` (extend 38→120) | +80 | Live limits discovery. |
| `tau_ai/fake.py` 41 | `agent/providers/fake.py` (new) | +40 | Test-only fake. |
| `tau_ai/tool_call_ids.py` 24 | `agent/tool_call_ids.py` (new) | +25 | `portable_tool_call_id`. |
| `tau_ai/openai_cache.py` 20 | `agent/openai_cache.py` (new) | +20 | `prompt_cache_key`. |
| `tau_coding/session.py` 3389 | `agent/coding_session.py` (new) | +3350 | `CodingSession` (largest coding file). |
| `tau_coding/tools.py` 1215 | `agent/tools/coding_tools.py` (new) | +1210 | `read/write/edit/bash` (+ `ImageSupportState`). |
| `tau_coding/image_processing.py` 253 | `agent/image_processing.py` (new) | +255 | Pillow-guarded normalization. |
| `tau_coding/provider_config.py` 2563 | `agent/provider_config.py` (new, keep `models.py` legacy) | +2500 | Durable config (atomic + backup). |
| `tau_coding/catalog_loader.py` 681 | `agent/catalog_loader.py` (new) | +680 | Builtin+overlay catalog. |
| `tau_coding/provider_catalog.py` 111 | `agent/catalog.py` (extend 16→111) | +100 | Typed `ProviderCatalogEntry`. |
| `tau_coding/provider_runtime.py` 349 | `agent/provider_runtime.py` (new) | +350 | `create_model_provider`. |
| `tau_coding/credentials.py` 241 | `agent/credentials.py` (new) | +240 | `FileCredentialStore`. |
| `tau_coding/session_export.py` 1689 | `agent/session_export.py` (extend 130→1689) | +1560 | Artifact export (HTML+JSON). |
| `tau_coding/session_manager.py` 348 | `agent/session_manager.py` (extend 206→348) | +150 | Indexed `CodingSessionRecord` + `history_from_records`. |
| `tau_coding/session_stats.py` 146 | `agent/session_stats.py` (extend 66→170) | +100 | Tiered cost stats. |
| `tau_coding/session_usage.py` 920 | `agent/session_usage.py` (extend 228→920) | +700 | Usage overlay. |
| `tau_coding/context.py` 95 | `agent/context.py` (replace stub 8) | +95 | `discover_project_context_with_diagnostics`. |
| `tau_coding/context_window.py` 353 | `agent/context_window.py` (extend 99→353) | +260 | Token estimators + compaction threshold. |
| `tau_coding/diagnostics.py` 163 | `agent/diagnostics.py` (extend 120→190) | +70 | `AgentCallDiagnosticLogger.from_paths`. |
| `tau_coding/resources.py` 331 | `agent/resources.py` (new) | +330 | `TauResourcePaths`. |
| `tau_coding/paths.py` 130 | `agent/paths.py` (extend 60→130) | +70 | `TauPaths` + `TauResourcePaths` factory. |
| `tau_coding/project_trust.py` 674 | `agent/project_trust.py` (extend 502→700) | +200 | `ExtensionTrustResult` seam. |
| `tau_coding/prompt_templates.py` 217 | `agent/prompt_templates.py` (extend 222 + add diagnostics) | +20 | `load_..._with_diagnostics`. |
| `tau_coding/skills.py` 255 | `agent/skills.py` (replace stub 23→255) | +240 | Skill discovery + `expand_skill_command`. |
| `tau_coding/system_prompt.py` 210 | `agent/system_prompt.py` (new) | +210 | `build_system_prompt`. |
| `tau_coding/thinking.py` 90 | `agent/thinking.py` (patch 164 + per-model map) | +30 | Wire `thinking_level_map`. |
| `tau_coding/branch_summary.py` 214 | `agent/branch_summary.py` (extend 157→214) | +60 | `custom_instructions` semantics. |
| `tau_coding/reload.py` 31 | `agent/reload.py` (already 87 — verify) | +10 | Parity check. |
| `tau_coding/shell_config.py` 74 | `agent/shell_config.py` (new) | +75 | `load_shell_settings`. |
| `tau_coding/commands.py` 876 | `agent/commands.py` (extend 538→876) | +350 | Flag merge + `/login`/`/tools` etc. |
| `tau_coding/events.py` 91 | `agent/events.py` (extend above) | +30 | `CodingSessionEvent` union. |
| `tau_coding/update_check.py` 379 | `agent/update_check.py` (new) | +380 | PyPI poll. |
| `tau_coding/updater.py` 387 | `agent/updater.py` (new) | +385 | `install_update`. |
| `tau_coding/version.py` 16 | `agent/version.py` (new) | +15 | `current_version`. |
| `tau_coding/cli.py` 1121 | `agent/cli.py` (new) + `agent/main.py` (keep 563) | +500 net | `CodingSession.load` dispatch; keep prover subcommands. |
| `tau_coding/rendering/*` (185) | `agent/rendering/{base,json,plain,transcript}.py` (new dir) | +190 | Transcript+JSON+plain. |
| `tau_coding/extensions/api.py` 1001 | `agent/extensions/api.py` (new) | +1000 | `ExtensionAPI` + `ComponentBridge`. |
| `tau_coding/extensions/runtime.py` 943 | `agent/extensions/runtime.py` (new) | +945 | `ExtensionRuntime` dispatch + hooks. |
| `tau_coding/extensions/loader.py` 350 | `agent/extensions/loader.py` (new) | +350 | Discovery + `sys.modules` purge. |
| `tau_coding/oauth.py` 527 | `agent/oauth/oauth.py` (replace stub 14) | +530 | PKCE + local server. |
| `tau_coding/oauth_anthropic.py` 285 | `agent/oauth/anthropic.py` (new) | +285 | Anthropic OAuth. |
| `tau_coding/oauth_github_copilot.py` 285 | `agent/oauth/github_copilot.py` (new) | +285 | Copilot device flow. |
| `tau_coding/oauth_device.py` 109 | `agent/oauth/device.py` (new) | +110 | Device polling helper. |
| `tau_coding/oauth_registry.py` 55 | `agent/oauth/registry.py` (new) | +55 | Registry (3 built-ins). |
| `tau_coding/oauth_types.py` 127 | `agent/oauth/types.py` (new) | +130 | `OAuthProvider`, `OAuthLoginCallbacks`. |
| `tau_coding/rpc.py` 798 | `agent/rpc.py` (replace stub 7) | +800 | `RpcServer` + all command types. |
| `tau_coding/tui/app.py` 7128 | `agent/tui/app.py` (new — keep `agent/tui.py` as re-export 2055) | +3800 net | `TauTuiApp` + dialogs; ProverApp as subclass. |
| `tau_coding/tui/widgets.py` 2604 | `agent/tui/widgets.py` (new) | +2600 | `SessionSidebar`, `TranscriptView` bounded window. |
| `tau_coding/tui/state.py` 918 | `agent/tui/state.py` (new) + `agent/compaction.py` keep | +900 | `TuiState` batching/grouping. |
| `tau_coding/tui/adapter.py` 154 | `agent/tui/adapter.py` (new) | +155 | `TuiEventAdapter`. |
| `tau_coding/tui/autocomplete.py` 579 | `agent/tui/autocomplete.py` (new — extend stub 56) | +530 | `build_completion_state`. |
| `tau_coding/tui/config.py` 207 | `agent/tui/config.py` (new) | +210 | `TuiSettings`, `TuiKeybindings`, custom themes. |
| `tau_coding/tui/file_drop.py` 83 | `agent/file_drop.py` (73→83) | +10 | Edge tests. |
| `tau_coding/tui/project_trust.py` 184 | `agent/tui/project_trust.py` (new — lean TrustScreen 100→) | +90 | `prompt_project_trust` full. |
| `tau_coding/tui/terminal_title.py` 124 | `agent/terminal_title.py` (94→124) | +30 | Throttled title updates. |
| `tau_coding/tui/terminal_notification.py` 115 | `agent/terminal_notification.py` (116 — done) | +5 | Done. |
| `tau_coding/self_docs.py` 23 | *(inline)* | +20 | Docs embed. |
| `tau_coding/rendering` already counted | `agent/rendering/` | — | — |

**File-count summary:** 72 files require work (15 new `agent/session/` + `types` + 17 new `providers/*` + ~20 new `agent/coding_session*` substrate + 12 new `extensions|oauth|rpc` + 11 new `tui*`/`rendering` + 3 updated lean stubs). ~30 new modules, ~40 edits to existing.

---

## 11. Effort, Risk, Verification

### Sequencing

* **Weeks 1-2 — Phase 12 (Agent Core):** Ports `tau_agent` verbatim; prove-loop shim validates `repair_tool_history` parity. No TUI impact — lean tests should stay green via `agent/prover_loop.py` alias.
* **Weeks 3-5 — Phase 13 (Provider Fleet):** Parallelizable with Phase 12 tail. Adds `httpx` to `pyproject.toml` (`httpx[http2]>=0.27`, `anyio>=4`). Keeps `openai` SDK as dev-dep for legacy `llm.py`. Risk: `openai_responses` parser needs 100% SSE fixture coverage — add `tests/providers/fixtures/{chat, responses}.jsonl`.
* **Weeks 6-9 — Phase 14 (Coding Session):** Critical path. Review gate: line-diff `session.py:362-560 load()` against lean `coding_session.py`. Temporary flag `PROVER_USE_CODING_SESSION=1` lets TUI opt-in without breaking benchmark runs.
* **Weeks 10-12 — Phase 15 (Extensions+OAuth+RPC):** Depends on 14 stable. Add `python -m agent.rpc` smoke test (pipe 4 commands → asserts `response.success==true`). Extension tests: `setup(tau) registers tool → prompt triggers tool → trust decider` trio.
* **Weeks 13-16 — Phase 16 (TUI merge + CLI):** Longest QA tail — manual `prover tui` open runs under `PROVER_TRUST=ask` and headless `prover prove 'theorem …'` regression.

### Cross-cutting deps

* `httpx` + `anyio` (Phase 13) are required before Phase 14 (`credential_resolver` await).
* `Pillow` optional (`pip install lean-prover[vision]` extra) — `image_processing.py` docstring must cite it; CI skips via `pytest.mark.skipif(not has_pillow)`.

### Verification matrix

| Area | Tau source tests to port | Lean-specific regression |
|------|--------------------------|--------------------------|
| `loop`/`harness` | `tests/tau_agent/test_loop.py::test_steer_mid_turn` , `test_max_turns`, `test_tool_blocked` | `prover prove` still proves `sq_nonneg` (hammer prepass) |
| `tool_history` | `test_repair_tool_history_orphan_tool_call` (orphan `ToolCall` → auto-error result) | `loop.prove` resume mode (orphan in `history_from_records`) |
| `session` storage | `test_jsonl_u2028_not_split` | `sessions_dir()` index migration (`models.json`→`providers.json`) |
| `openai_compatible` | `test_chat_parser_reasoning_content` , `test_responses_finish_reason` | `PROVER_LEMMA_PLAN=1` still prepends `lemma_bank` |
| `extensions` | `test_extension_generation_stale_raises`, `test_component_slot_replace` | Headless `prover prove --no-extensions` flag |
| `oauth` | `test_pkce_verifier_challenge_b64url`, `test_local_server_state_mismatch` (mock `.shutdown`) | `prover login --help` lists `openai-codex anthropic github-copilot` |
| `rpc` | Pi JSONL golden file `tests/rpc/golden.jsonl` (dispatch all 19 types) | `prover rpc` under `anyio.run` doesn't double-cancel on abort |
| `tui/state` | `test_tui_state_batched_tools`, `test_grouped_file_tool` | `prover tui` opens with `bench/problems.json` missing (search hint shows) |

### Risk register

* **R1 — `CodingSession.load` ordering** (High): trust must resolve before `resources` + extensions before `build_system_prompt`. Mitigate: side-by-side diff review + taped stack-trace on wrong order (Tau throws `TrustPrompt required but no interactive`).
* **R2 — Streaming parser drift** (High): reasoning/thinking merge differs across providers. Mitigate: identical parser class names, shared golden fixtures committed in-repo.
* **R3 — TUI merge breakage** (Med-High): lean's benchmark list assumes `ListView` indices map 1:1 to filtered pool. Tau's windowed transcript `mount_before` pattern can desync `ListView.index`. Mitigate: additive tabs, keep problem list `ListView` un-windowed.
* **R4 — Credential path confusion** (Med): `~/.tau` vs `~/.prover`. Lean already uses `~/.prover`; keep it but add `TAU_HOME` env fallback reading `~/.tau` if `~/.prover` absent (migration helper).
* **R5 — `harness.subscribe` vs lean sync `prove(on_event)`** (Med): Lean `prove()` is sync with callback `on_event(dict)`; Tau `Harness.subscribe` is async. Mitigate: `prover_loop.py` bridges by collecting `AgentEvent` queue and fan-out via `_event_to_dict` adapter (keep lean trace shape `{"event":"hammer"...}`).

---

## 12. Checklists

### Per-file DoD (apply to every row in §10)

- [ ] File ported line-for-line before Lean adaptation (name every translation: e.g. `anyio`→`asyncio`, `pydantic BaseModel`→`dataclass(frozen,slots)` where chosen — document divergence in file docstring).
- [ ] Docstring cites Tau source commit `37a9e43` + original `src/...` path.
- [ ] Type aliases exported (`JSONValue`, `ProviderConfig`, `TuiThemeName`) re-exported at package root for import parity.
- [ ] Unit tests ported from Tau (or new when Tau has integration coverage only) — coverage ≥90% for that file.
- [ ] Lean fork points flagged with `# Lean adaptation:` comment referencing §9 row.
- [ ] Fails CI with `mypy --strict` (Tau uses `py.typed` on every package; lean-prover must match).

### Phase exit criteria

* **Phase 12 done** when `agent.loop.run_agent_loop` passes `tau_agent` test clones and `prove("theorem foo:…")` still proves via `prover_loop`.
* **Phase 13 done** when `agent.providers.openai_compatible.OpenAICompatibleProvider.stream_response` replays recorded Claude/Gemini SSE and `llm.model()` reads `ProviderSettings` (not `models.json` dict).
* **Phase 14 done** when `await CodingSession.load(config)` + `session.branch_to_entry(entry_id, summarize=True)` round-trips with `MockProvider`; lean TUI can `new_session()` + reload without data loss.
* **Phase 15 done** when `examples/extensions/hello_tool.py` (Tau `data/examples/extensions/hello_tool.py`) registers `/hello` + `read` hook, survives `/reload`, and `prover login openai-codex` PKCE prompt shows URL in TUI `ExtensionInputScreen`; `echo '{"type":"get_state","id":1}' | prover rpc` returns `{"success":true}`.
* **Phase 16 done** when `prover tui` shows both benchmark problem list and transcript `GroupedToolCall` edit batches (`→ Editing 3 files · 2/3 complete`), `/tools` palette filters, `/tree` picker branches, `/export html` artifact matches Tau export checksum, and existing `prover prove|benchmark` benchmarks pass.

---

## Appendix — Hard numbers for `TAU_FULL_PORT_PLAN.md` front-matter

```yaml
tau_commit: 37a9e43
tau_files: 96
tau_loc_py: 42023
lean_agent_files_py: 32
lean_loc_py: 9830
remaining_loc_to_port: 32200      # 42023 - 9830 + divergent 1400
new_loc_estimate_full_fidelity: 22400  # +30200 when counting divergent prover extras retained
phases: [12,13,14,15,16]
eng_weeks: 16
new_modules: 30
edited_modules: 40
```

---

*Next action:* write this markdown to `TAU_FULL_PORT_PLAN.md` at repo root, then create a tracking issue per phase (labels `phase-12`…`phase-16`) and seed each with its file checklist from §10. Start Phase 12 with `agent/types.py` + `agent/provider.py` + `agent/tool_history.py` — they unblock everything and are pure logic with no I/O.*


</task_result>