---
description: Agent guide for CardLab
alwaysApply: true
---

# CLAUDE.md

Guidance for agents working in this repository.

## Project overview

CardLab (repo: `ai-card-game-lab`) is a local research tool for AI-vs-AI card games: run games, observe decisions, collect data, and fine-tune small models.

The primary workspace is **research** (`studies`), organizing a question, multiple experiment runs and related comparison records. An experiment is a fixed set of player configs plus a target game count. Record a hypothesis, run games, review decisions and publish conclusions under comparison snapshots. Training is optional under Analyze. Trial games (no experiment; zh: 试玩对局) still exist on `/game`.

Monorepo:

| Workspace | Stack |
|-----------|--------|
| `server/` | Python 3.11+ / FastAPI / Poetry / aiosqlite |
| `web/` | Vue 3 + TypeScript / Vite / Tailwind v4 / Reka UI |

Default frontend port is `5173` (proxies `/api` and `/api/v1/games/ws` to `localhost:8000`).

Desktop uses the same web/backend implementation. Native lifecycle coordination lives in
`desktop/src-tauri/src/close_state.rs` and `lifecycle.rs`: all research windows acknowledge
persisted drafts before the main window offers exit confirmation. Frontend lifecycle hooks
subscribe to the current WebviewWindow, never global close events. Only the exact owned
backend origin receives acknowledgment/cancel and event-listener capabilities; no frontend
process-exit or generic filesystem commands. Prompt A/B registers an unfinished-design
blocker; do not add another draft persistence path. Run `cargo test` and `cargo clippy
--all-targets -- -D warnings` from `desktop/src-tauri` when changing host behavior.

Main-window research resume uses `desktop/src-tauri/src/workspace.rs` and
`web/src/stores/useDesktopWorkspace.ts`. Only main receives read/save workspace capabilities.
Route metadata `desktopResume` owns the query allowlist; never persist full origins, session
tickets, creation triggers or editor content. Navigation updates memory; normal close flushes
the fixed app-data `workspace.json` before acknowledging. Startup restores before mounting
editors. Evidence windows and browser use do not read/write this record. Late navigation
revokes close readiness. Keep research drafts in their existing SQLite service.
The same required workspace record also contains `window` (normal rectangle and maximized
state). `window_layout.rs` captures/restores it using GetWindowPlacement/SetWindowPlacement;
keep Windows workspace coordinates intact, never substitute screen-coordinate setters.
The host captures its own main window during save; JS never supplies geometry. Restore layout
before returning the route. Reject incomplete records without migration or another storage path.

JSON serialization uses `web/src/utils/jsonFile.ts`; JSON and readable HTML share
`exportFile.ts` transport and feedback. Await exports inside
async actions; do not show caller-side success before the native save resolves. Desktop
`save_export` in `export.rs` accepts only a suggested basename, content and the fixed
`json`/`html` format (32 MiB maximum), then uses
the owning window's system save dialog. It never accepts a destination path from JS.
Export/close reservations share Coordinator. `file_io.rs` provides the single atomic file
replacement helper for exports and workspace locations; do not add a parallel write path.
The save command returns a host-owned record ID or null for cancellation. Each window keeps
only its latest saved path in native memory; `reveal_saved_export` takes that ID, checks the
calling window, and uses Windows `SHOpenFolderAndSelectItems` with one absolute item PIDL
and a zero selection-array count. Balance COM initialization and release the PIDL; return
native failures without a fallback. Reuse the existing windows-sys dependency. Never expose opener IPC
or accept JS paths. Forget records when windows are destroyed. The shared success Toast owns
the explicit reveal action, waits for it, and keeps retry available after reveal errors.

## Commands

### Dev servers (repo root `scripts/`)

| Platform | Backend | Frontend |
|----------|---------|----------|
| Windows | `scripts\start-backend.bat` | `scripts\start-frontend.bat` |
| macOS / Linux | `./scripts/start-backend.sh` | `./scripts/start-frontend.sh` |

E2E wrapper: `scripts/e2e_pipeline.ps1` / `scripts/e2e_pipeline.sh` (calls `server/scripts/e2e_pipeline.py`).

### Backend (`server/`)

```bash
cd server
poetry install
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
poetry run python -m app.mcp   # stdio MCP (Cursor); logs on stderr
# HTTP MCP: /mcp/ on API when MCP_HTTP_ENABLED=true (default)
# or: poetry run python -m app.mcp --transport streamable-http --port 8001
poetry run pytest
poetry run pytest --cov=app --cov-report=term-missing --cov-fail-under=80
poetry run pytest tests/test_api/test_system.py
poetry run pytest -k "test_health"
poetry run ruff check .
poetry run ruff format .
poetry run ruff format --check .
poetry run mypy app/core
poetry run mypy app/core app/services
poetry run mypy app/
```

Training extras (PEFT LoRA): `poetry install --with training`.

CI (`.github/workflows/ci.yml`): `ruff check` → `ruff format --check` → `mypy app/core app/services`
(`app.core.training.*` ignored) → `pytest --cov=app --cov-report=term-missing --cov-fail-under=80`.
Frontend CI unchanged.

### Frontend (`web/`)

```bash
cd web
npm install
npm run dev
npm run build
npm run lint
npm run lint:ci
npm run format
npm run type-check
npm test
```

CI: `npm run lint:ci` → `npm test` → `npm run build` (build already runs `type-check` for application code, unit tests and E2E tests via `tsconfig.test.json`).
E2E smoke (separate CI job): `npm run test:e2e` — demo → experiment verdict
(starts backend + Vite via Playwright `webServer`).
## Architecture

Strict one-way backend dependency:

```
API (app/api/) → Service (app/services/) → Repository (app/repositories/) → database
                                         → Core (app/core/)
```

- **API** — routes, validation, serialization. Never call Core or Repository.
- **Service** — orchestration. Singletons do not hold DB connections; background work opens its own connection. `ExperimentService` is a facade over `ExperimentCollectMixin` + `ExperimentDeltaMixin` (`experiment_collect.py` / `experiment_delta.py`); exceptions live in `experiment_errors.py`. Public API / DI still import `ExperimentService`.
- **Repository** — SQLite via aiosqlite.
- **Core** — framework-independent domain logic:
  - `engine/` — `GameEngine` ABC + `EngineCapability` + `GameEngineRegistry`. Engines are stateless; state is `GameState`. First engine: Dou Dizhu (`doudizhu`). Game-specific hand analyzers live under the engine package (e.g. `engine/doudizhu/hand_analyzer.py`), not `core/ai/tools/`. `EngineCapability.display_name` and `GameEngine.default_system_template(phase)` own prompt fallbacks; `PromptBuilder` does not hardcode a game id.
  - `engine/observer_types.py` — `ObserverSnapshot` protocol for the observer UI.
  - `ai/` — `LLMClient` ABC + `LLMClientFactory`. Two implementations: `OpenAICompatibleClient` (OpenAI, DashScope, DeepSeek, Kimi, Zhipu, Yi, Baichuan, MiniMax) and `OllamaClient`. Wired in `dependencies.py`. Streaming uses `stream_options: {"include_usage": true}`; final `StreamChunk` may carry `usage`. Clients accept `response_format` and degrade (drop `stream_options`, then `response_format`) only when a 400/422 explicitly identifies that field as unsupported; `OllamaClient` translates it to Ollama's `format`. There is **no** proactive per-provider capability probe or cache — only reactive degrade. Authentication/validation failures and rate limits are non-retryable within a decision: neither streaming fallback nor policy loops may turn them into another immediate request. Rate limits remain typed `AI_RATE_LIMIT_EXCEEDED` errors. Optional **VCR** wrapper (`core/ai/vcr.py`): `VCR_MODE=record|replay` stores/replays chat calls as JSONL under `data/vcr/` (match key = SHA-256 of provider + messages + model/sampling/`response_format`); `replay` miss raises `VcrMissError` (no silent live call). Default `off`. `core/ai/tools/` serializes decision tool output for traces and live observation. The Dou Dizhu engine owns `analyze_hand`.
  - `policy/` — `Policy` ABC: an async **event stream** (`ThinkingDelta` / `ToolCall` / `ToolResult` / `LlmRequest` / `LlmUsage` / `ActionChosen`) ending in exactly one `ActionChosen`. `LLMPolicy` owns single-shot ask-and-parse; `ToolLoopPolicy` (`tool_loop`) ReAct-calls engine tools then picks an id; `SearchAugmentedPolicy` (`search`) proposes ≤k candidates then scores via rollout. `HeuristicPolicy` / `FirstActionPolicy` / `RandomPolicy` are the non-LLM baselines. Live seats pick a policy via player-config `policy_kind` (`AIService`); preflight skips provider checks for baseline seats. A `Budget` caps LLM and tool calls; `PolicyContext` injects `EngineAdvisor`, `PromptSource`, optional `score_actions`, and the rng.
  - `eval/` — `rollout.py` scores candidate actions by determinized rollouts with common random numbers. Experiment-level **Scorer** plugins (`build_scorer_registry(game_type=…)`) cover every Dou Dizhu `eval_metric_id` (`train_usable`, `parser_success`, `latency_p50_p95`, `role:landlord`, `ev_loss`); `ExperimentService` overlays results onto summary from `protocol.scorer.eval_metric_ids`. Repo `eval_aggregates` supplies counts only (Dou Dizhu seat-as-landlord from the SQLite `game_seat_results` view); rate formulas live in Scorers. **Puzzle packs** (`puzzle.py` / `replay.py` / `perturb.py` + `PuzzleService`): extract high-spread decisions into `{data_dir}/puzzles/{pack_id}/`, score baselines offline, and **probe** consistency under legal-action / hand-card order shuffles (`POST .../probe`). Minimal Analyze UI at `/pipeline/puzzles`.
  - `collector/` — JSONL writer.
  - `training/` — ChatML export + PEFT LoRA SFT (`sft.py`), optional 4-bit QLoRA, CPU-smoke clamps, deploy/GGUF/Ollama helpers. **Preference (DPO) export** (`preference.py` + `DecisionService.export_preferences`): chosen = rollout `best_action_id`, rejected = model `action_id`; simulation-derived preference labels live in `evaluator_params` at score time (no new columns). Missing training deps refuse task creation. Status: `pending` → `exporting` → `training` → `completed` / `failed` / `cancelled`. There is no project-level `Trainer` ABC.
  - `events/` — in-process `EventBus` + game lifecycle events.
  - `env/` — duck-typed PettingZoo-style **AEC** wrapper (`CardLabAECEnv`): `reset` / `agent_iter` / `last` / `step(index)`; non-learner seats use an injected baseline `ActionSelector` (default heuristic). No hard `pettingzoo` dependency. Reward from `engine.terminal_rewards()`.
- **WebSocket** (`app/websocket/`) — `ConnectionManager` broadcasts per-game events; `handlers.py` is the WS endpoint.
- **MCP** (`app/mcp/`) — Model Context Protocol server (official `mcp` 2.x `MCPServer`). Tools call Services directly: read `list_experiments`, `get_experiment` (games off by default), `list_decision_points`, `get_decision_stats`; write `start_collect` / `cancel_collect` (may spend API budget). **stdio:** `python -m app.mcp` (logs on stderr). **HTTP:** Streamable HTTP mounted on the API at `/mcp/` when `MCP_HTTP_ENABLED=true` (default), or standalone `python -m app.mcp --transport streamable-http --port 8001`. Cursor stdio example:

```json
{
  "mcpServers": {
    "cardlab": {
      "command": "poetry",
      "args": ["run", "python", "-m", "app.mcp"],
      "cwd": "<repo>/server",
      "env": {
        "SQLITE_PATH": "<repo>/data/db/app.db",
        "DATA_DIR": "<repo>/data"
      }
    }
  }
}
```

- **Schemas** (`app/schemas/`) — Pydantic request/response models. Shared `ApiResponse` / `PaginatedData`.
- **Config** — `app/config.py` (`pydantic-settings`) from env / project-root `.env`. Player configs live in SQLite and are created in the Player configs UI (`/experiment-configs`); each has `policy_kind` (`llm` default; `tool_loop` / `search` for LLM variants; or `heuristic` / `random` / `first` baseline — no API). There is no YAML seed.

## Frontend

- Vue 3 `<script setup lang="ts">`, Pinia, Vue Router, vue-i18n (`zh-CN` + `en`). New user-facing copy goes through i18n. Locale messages live under `src/i18n/locales/{zh-CN,en}/` (`common` / `guide` / `experiment` / `game` / `analyze` / `settings`); thin `locales/zh-CN.ts` / `en.ts` re-export the merge.
- `src/api/` — typed Axios client (`client.ts` normalizes errors). Domain modules: `experimentApi`, `experimentConfigApi`, `gameApi`, `dataApi`, `decision`, `traces`, `trainingApi`, `prompts`, `systemApi`, `archive`.
- `src/stores/` — `useDataStore`, `useTrainingStore`.
- `src/composables/` — `useWebSocket`, `useGameWebSocket` (observer), `usePagination`, `useTweenNumber`, `useFieldWidth`, `useTheme`, `useLocale`.
- Dual shells:
  - `WorkbenchLayout.vue` — six destinations: Research / All runs / Players / Trial games / Analyze / Settings (zh: 研究工作室 / 全部运行 / 选手配置 / 试玩对局 / 分析 / 设置). Analyze is a hub (`/pipeline/{data,decisions,training,traces,puzzles}`). Prompts stay at `/prompt`, linked from Settings. Route swap is immediate (no page `Transition`; it raced with overlay unmount). Do not wrap the observer shell. Layout owns the page title; list pages should not repeat an in-page subtitle. Brand logo at `/logo.png` in sidebar header. **Usage guide** (`/guide`) is header-only via `HeaderToggles` (book icon), not in the sidebar.
  - `ObserverLayout.vue` — fullscreen watch / replay.
- UI kit: `components/ui/*` (Reka UI + Ink Lab tokens in `styles/tokens.css`, motion in `styles/motion.css`). Density helpers: `KpiStrip`, `NameChips`, `CompactRecordList`. Charts: ECharts.
- Design baseline (`styles/tokens.css`): font sizes come **only** from the six-step
  scale (`--ink-text-caption/body/lead/title/headline/verdict`, exposed as
  `text-caption` … `text-verdict`); spacing from `--ink-space-*` (`p-ink-4`, `gap-ink-3`).
  Hierarchy is expressed with size and weight, not with extra borders and fills:
  `.ink-card` has no shadow, `.ink-layer` is for floating layers only, and `.ink-section`
  groups with whitespace. There is a single row density — `UiTable` has no `density` prop.
  `--ink-evidence-*` renders a claim's confidence (weak claims look weak); it is never
  a good/bad hue.
- Experiment detail is a **five-phase workbench**: `resolveStageId()` (`utils/experimentStage.ts`) picks
  one of `empty` / `collecting` / `harvest` / `control` / `verdict`, and `ExperimentStage.vue`
  renders exactly one phase — a status sentence plus a single next step (`StageAction.vue`,
  or `StageVerdict.vue` for the verdict). The verdict opens the shared notebook editor.
  **Generate working summary** in `ExperimentNotebookPanel.vue` calls
  `POST /api/v1/experiments/{id}/conclusion-draft` (template text from `core/research/conclusion_draft.py`;
  no LLM). Both notebook and comparison editors persist drafts through the shared SQLite draft API;
  autosave never publishes formal research revisions. Applying notebook fields via `PATCH` checks
  `expected_draft_revision` in the write transaction. Generated `blunders` appear in the notebook
  with deep links to `/pipeline/decisions?experiment_id=&decision_id=`.
  Detail keeps the current task in the main area. Games, player/scenario results, timeline,
  benchmark and conditions open on demand in the shared side panel; notebook editing uses
  that same dialog component and the existing persistent draft. Starting collection opens
  an explicit confirmation dialog. Do not restore the previous stacked reports.
- Run-level scenario browsing uses `ExperimentScenarios` in the existing side panel and
  `GET /experiments/{id}/scenarios`. The API reads one transaction, reuses `SCENARIO_SQL`,
  and restricts all groups, games and decisions to the same run. Counts describe current
  records, including unfinished games; they are not frozen paired samples. Never equate
  decisions with independent observations, sum game counts across groups, rank estimates
  from different evaluation settings, or present action-selected subsets as causal evidence.
  `scenarioNavigation.ts` owns validated positions and return links. Keep original context
  in `scenario_run` and the `scenario_*` query fields; desktop persistence uses the same route
  allowlist. Missing selections must be explicit, not silently replaced. See `batch-3b.md`.
- Decision details can create one-position test packs through `DecisionPuzzle` and
  `PuzzleService.decision_source/from_decision`. `puzzle_source.py` verifies continuous
  recorded history against seeded replay and freezes existing estimates; it never runs
  new rollouts. At least two legal actions and complete stored evaluation parameters are
  required. Canonical action IDs identify bid targets, which older stored menus omit;
  explicit targets, when present, must agree. POST rechecks the inspected source hash.
  Keep provenance in pack `extract` metadata, reuse run/probe scoring, and never equate
  a selected case or repeated perturbations with independent validation. `puzzle_pack`
  preserves the return link from decisions. See `batch-4c.md`.
- Saved two-run Dou Dizhu comparisons use `ComparisonReplay`: frozen jointly valid deals,
  a shared recorded-decision timeline and pair citation into the existing draft. `DecisionPreview`
  is shared with individual review. Alignment lives in `core/research/decision_alignment.py`;
  pre-action boards reuse `services/decision_replay.py` with position-test provenance checks.
  Only a continuous verified prefix is displayed; version mismatch or a gap stops that side.
  GenericBoard defaults to acting-player information; explicit researcher hands are reconstructed,
  not historical actor-visible input. `EvidenceCitationEntry` lists eligible frozen comparisons for decisions, saved position tests and invocation records,
  and `review_decision` opens a scope-checked preview without mutating drafts. Explicit additions
  reuse `EvidenceCiteButton` and the existing comparison draft. See `batch-3d.md`.
  Never guess missing records or rejoin a shared path after divergence or a gap. Only
  `coverage.members` supplies candidate/citation scope. Details are in `batch-3a.md` under
  `specs/desktop-research-workspace`. Other comparisons use individual evidence review.
- Invocation citations use `research_traces.py`, the shared chooser and comparison draft.
  Check frozen cohort membership, owner, seed, players and timezone-aware cutoff before review
  and publication. Recheck the content hash in the publication transaction, then retain a copy
  of saved input/output/metrics/spans. Source status must not overwrite published content.
  Up to five distinct records, 2 MiB each and 8 MiB total; never truncate. A changed hash requires
  fresh review and explicit update preserving the note. Traces are diagnostics, not extra
  independent samples or proof of internal reasoning. Exact `trace_id` browsing must respect
  all active filters and preserve `report_id/trace_evidence`. See `batch-3f.md`.
- A blocking preflight check **replaces** that phase's status line and action rather than sitting in a
  banner above a button that only warns. Only `severity: warn` renders as a notice.
- Observation uses **one** `GenericBoard` seat grid (center table + surround seats). Do not add `components/game/boards/<Game>Board.vue` or branch `GameObserverView` by `game_type`.

### Routes

| Path | View |
|------|------|
| `/` | `StudyHomeView` (research list, question preview and continue entry) |
| `/research/:id` | `StudyWorkspaceView` (question, runs and related comparison records) |
| `/experiments` | `ExperimentListView` (all runs, first-run checklist and shared creation form) |
| `/experiments/:id` | `ExperimentDetailView` (detail page; stage workbench with primary CTA) |
| `/experiments/compare` | `ExperimentCompareView` |
| `/pipeline` | `PipelineView` (Analyze hub; opens `/pipeline/data`) |
| `/pipeline/data` | `DataView` |
| `/pipeline/decisions` | `DecisionView` |
| `/pipeline/training` | `TrainingView` |
| `/pipeline/traces` | `TraceView` |
| `/pipeline/puzzles` | `PuzzleView` (baseline packs; extract / run / probe) |
| `/game` | `GameView` (trial games — zh: 试玩对局) |
| `/game/:id` | `GameObserverView` (Observer shell) |
| `/experiment-configs` | `ExperimentConfigView` |
| `/prompt` | `PromptView` (linked from Settings; not in the sidebar) |
| `/settings` | `SettingsView` (read-only: providers, paths, storage, thinking-budget defaults, EV opponent / self-proxy, memory scope; preflight via `GET /api/v1/system/preflight`) |
| `/guide` | `GuideView` (usage guide: modules, flow diagrams; TOC on the right on desktop) |

Only canonical Analyze routes are supported; old bare tool routes and `/ai-players` are removed.
Prompt templates link to study-based frozen-baseline designs; there is no all-history version comparison.
Trace list and metrics share AND-combined filters and timezone-aware inclusive bounds. Latency
aggregates count only finite nonnegative numbers; parse rates use explicitly boolean statuses.
Missing measurements remain null. Charts show the latest 200 records in a fixed window while
aggregates cover the entire window. These are runtime diagnostics, not independent research samples.
See `specs/desktop-research-workspace/batch-2c.md`.

Deep links (`?experiment_id=`, `?game_id=&decision_id=`) keep the query. The Analyze hub owns the experiment context bar.

## Experiments

- Table `experiments` includes `hypothesis`, `conclusion`, `tags` (JSON array), plus existing `notes` and frozen `protocol`.
- `games.experiment_id` is nullable (trial games on `/game` stay outside experiments).
- Collect accepts an optional `idempotency_key` (1–128 chars). Reserve games + seed protocol + request record in one transaction before launching any games; retries reuse the batch and only start `created` games. A reused key with a different count returns 409. Keep the frontend key until the response succeeds. See `docs/API_DESIGN.md`.
- Creating an experiment does **not** start games (avoids accidental API spend). Start the experiment from the detail page.
- Home (`/`) organizes research. `studies` / `study_runs` maintain one owner per run; quick runs auto-create research, copies and paired controls inherit ownership. StudyService reuses ExperimentService for run summaries; comparison membership is derived from all frozen member IDs, without duplicating records. See `specs/desktop-research-workspace/batch-2a.md`.
- Research tasks (`ResearchOperations`) switch between games (`StudyOperations`, `GET /studies/{id}/operations`) and training (`StudyTrainingOperations`, existing `GET /training/tasks`). Game filters apply before 20-run pagination; zero, missing and invalid token fields differ. Never derive missing totals or add spans/rounds again. Training ownership follows only saved `experiment_id` and `study_runs`; study/run/task/state filters combine before task pagination in one read transaction. Progress must be finite within 0–1; damaged config/result objects are explicit. Saved usage is not billing or independent samples, and training completion is not model improvement. The game/training lists are read-only; existing run/training controls remain authoritative. URL `panel=operations`, `task_kind`, `task_state`, `task_page` plus `task_study` and exact training `study_id/experiment_id/task_id` preserve location and are desktop-resume allowlisted. See `specs/desktop-research-workspace/batch-5f.md` and `batch-5g.md`.
- Budget and expenses (`StudyFinance`, `task_kind=finance`) reuse the study panel. Migration 7 stores immutable budget versions and user-entered expenses with retained void reasons. Use decimal strings / integer millionths, a fixed CNY/USD/EUR currency, required source/date/attribution, revision checks and idempotent expense requests. Never convert recorded tokens into costs or label the budget difference as an available balance. `ensure_study_budget` runs in the admission write transaction for collection reservations, game start/resume and linked training creation. Enabled limits block when registered costs reach the cap; accepted tasks continue, future costs are not reserved, and delayed/omitted expenses can exceed actual spending limits. Trial games, unlinked training and decision previews are outside scope. Form saves are explicit and use existing desktop-close blockers. See `specs/desktop-research-workspace/batch-5h.md`.
- Supplier costs (`StudyBilling`, migration 8) use the official OpenAI Costs API with separate server-only `OPENAI_BILLING_ADMIN_KEY` / `OPENAI_BILLING_ORGANIZATION_ID`, a fixed endpoint and no redirects. Scope each immutable snapshot by config revision, organization, project and UTC interval; parse exact decimal amounts, require all pages, retain failure attempts and never add historical snapshots together. Supplier USD limits and manual expense limits are independent admission checks, never added or converted. Enabled supplier limits also block missing, failed or stale snapshots; retrying a failed sync cannot unlock admission until success. Shared project costs are not automatically attributed to research or called complete/final billing. Manual sync and opt-in periodic plans share the same transactional claim. Migration 9 stores schedule versions and due times; bind each plan to an explicit cost configuration version. `BillingScheduler` runs only with the HTTP/desktop backend (30-second checks, at most 2 active jobs per process), resumes due plans without catch-up bursts, and cancels owned work on shutdown. Retry transient errors with bounded delays, suspend configuration/validation failures, and never let pausing a plan disable budgets. UI polls only for status and pauses during edits. See `specs/desktop-research-workspace/batch-5j.md`. Source lines and settings history stay reviewable in the existing study panel. See `specs/desktop-research-workspace/batch-5i.md`.
- `/research/:id/prompt-ab` designs one phase's prompt change from a complete frozen benchmark baseline. `prompt_design_service` verifies baseline and template fingerprints in a write transaction, deep-copies the protocol and uses ExperimentRepository to create B. Never re-snapshot live player settings for this flow. `protocol.design` records the declared change; existing protocol review automatically declares only matching prompt paths for that exact pair. Benchmark collection is bounded even with paired deals. Traces use the phase-specific frozen prompt version. See `specs/desktop-research-workspace/batch-2b.md`.
- The Prompt A/B wizard checks configuration, not remote connectivity, and never starts games. Its unsaved form has navigation/refresh protection but is not a persisted draft; experiment notes and comparison conclusions continue to use the shared draft service.
- Report follow-ups reuse this wizard with `baseline` and `source_revision` query parameters. The source conclusion stays at its exact revision; require a new user-authored hypothesis. Both preview and the create transaction check source membership and full frozen conditions. Persist only `protocol.design.source_revision_id` on the new variant, carry it into reserved holdout runs, and do not inherit it for ordinary designs. Source text is context, not new evidence; reusing development deals remains exploratory. See `specs/desktop-research-workspace/batch-4b.md`.
- All runs (`/experiments`): first-run checklist supports a baseline without model credentials, player configs and an experiment; **Load demo** seeds a main + control experiment pair (zero API) and opens `/experiments/exp_demo_main` at the verdict stage. Demo data is prepared evidence, not a newly executed experiment; trial replay game remains for `/game`. Import / compare live in a secondary menu; repo `examples/*.json` are importable experiment packs. Detail ⋯ **export** shares the experiment-pack format.
- `GET /experiments` includes `next_step` and a compact list `delta` (no `scenario_diffs`; keeps `this_decisive_n` / `peer_decisive_n` for sample context) so run lists resolve stages without N+1 detail fetches.
- Player count is validated against the engine `min` / `max` from `GET /api/v1/system/engines`.
- Detail phase priority is owned by `resolveStageId()`. Empty runs lead to start confirmation;
  collecting runs show progress/watch/cancel; harvest uses completed and valid game counts
  and leads to decision review; the verdict presents the evidence limit or supported direction.
  Training availability is not a gate for research. Conditions and notebook are separate
  on-demand panels; the overflow menu retains experiment-scoped Analyze links.
- The verdict headline uses `stage.evidence.*` when `can_conclude` is false. A supported
  verdict uses `delta.verdict_key`; Δ is never colored as good/bad. Paired sample and interval
  remain visible, while current scenario records have their own on-demand panel.
- Progress UI never shows an uncapped ratio like `14/10`. Use `formatExperimentProgress(finished, target)` (`stage.progressRatio` / `progressWithExtra`): display is capped at the target (`5/5 · 多跑了 9 局` / `5/5 · 9 beyond the target`). Collect may still finish more games than `target_games` on the backend.
- Δ cells have a `?` (`MetricHint`) linking to `/guide#metrics`. Formulas live in `metricHint.*` i18n and `guide.sections.metrics`. Changing an eval formula or verdict copy requires updating both. Δ is **not** colored good/bad.
- `collect_mode`: `free` (random seeds) or `benchmark` (fixed `deal_seeds` from `BENCHMARK_DEAL_SEEDS`, up to 50 games). Creating a benchmark run in the UI defaults `target_games` to the engine `benchmark_seed_count`. Collect must not go past the declared seed list (`ExperimentValidationError`); extra random seeds are not appended.
- Summary / compare expose eval metrics: role win rates, parser rate, train_usable, P50/P95 latency (from `rounds`), tokens/game, status counts, per-seat as-landlord win rate (needs `metadata.landlord_id`), plus `credibility` (decisive_n / CI width / low_power) and `scenario_scores` (bidding / playing / endgame / bomb: train_usable + parser). Collect CTA uses `GET /api/v1/system/preflight` (seat providers); Settings shows the same checks as a read-only machine-status page (keys stay in project-root `.env`), including thinking-budget defaults, `ev_loss_opponent_kind` / `ev_loss_self_proxy`, and `memory_scope`. UI copy comes from `preflight.*` by check `id` (not the backend `message`). Layout title for `/pipeline/*` is always `nav.analyze`. Experiment detail owns one identity bar with `HeaderToggles` (WorkbenchLayout skips its desktop toggles strip there). Collect confirms in a dialog with a batch stepper; while `collecting`, Stop games is a ghost secondary on the stage and also in the ⋯ menu — not a second primary CTA. Player configs are a card roster (win rate is not colored good/bad).
- `GET /experiments/{id}` adds computed `timeline`, `validation` (control runs + `control_progress` + `validation_ready`), `next_step` (`review_decisions` after collection regardless of training availability; `collect_control` → control experiment collect; `review` + `action=stay` when a control is ready — stay on the detail verdict, do not jump to compare), `delta` (vs source or first control: selected win-rate Δ, paired n, CI, optional `paired_p` / `paired_ci` from exact McNemar and a conservative Clopper–Pearson/Bonferroni difference interval, `can_conclude` / `inconclusive_reason`, `verdict_key`, plus per-scenario train/parser Δ), and `benchmark` (`null` unless `collect_mode=benchmark`: seed coverage of the declared `deal_seeds`). Create freezes from Settings into `protocol.solver.thinking_budget`, `protocol.solver.memory` (`none` \| `per_experiment`), and `protocol.scorer.evaluator` (EV knobs including `opponent_kind` / `self_proxy`). New decisions store `game_phase=endgame` when any remaining hand has ≤8 cards.
- `verdict_key` (`stronger` / `weaker` / `even` / `peer_pending` / `no_data`, from `_verdict_key()`) is the plain-language claim the UI renders as `stage.verdict.<key>` when `can_conclude`. It is computed server-side on purpose: an eval-formula change and its wording live in one place. `VERDICT_EVEN_THRESHOLD` decides when a gap is a tie. `verdictKeyOf()` derives the same key when the payload omits `verdict_key`.
- Completed training tasks for the experiment appear on `/pipeline/training?experiment_id=`; model repo can register an Ollama tag as a player config.

Main HTTP:

```
GET/POST /api/v1/experiments
PATCH    /api/v1/experiments/{id}
POST     /api/v1/experiments/{id}/clone
POST     /api/v1/experiments/{id}/conclusion-draft
GET      /api/v1/experiments/compare?ids=a,b
GET      /api/v1/experiments/{id}
GET      /api/v1/experiments/{id}/export
POST     /api/v1/experiments/import
POST     /api/v1/experiments/{id}/collect
POST     /api/v1/experiments/{id}/cancel-collect
POST     /api/v1/puzzles/extract
GET      /api/v1/puzzles/packs
GET      /api/v1/puzzles/packs/{pack_id}
POST     /api/v1/puzzles/packs/{pack_id}/run
POST     /api/v1/puzzles/packs/{pack_id}/probe
GET      /api/v1/system/benchmark-seeds
GET      /api/v1/system/preflight
```

While a collect is in flight (`summary.status=collecting`), Stop games (`cancel-collect`) is available as a ghost secondary on the stage and in the experiment detail ⋯ menu; it is not a second primary CTA. Control experiments (`pair_deals`) keep `collect_mode=free` — same-deal validation, not a benchmark coverage report.
Decision export, trace list, `GET /api/v1/data/stats`, and `POST /api/v1/datasets/from-decisions` accept `experiment_id`. Datasets are registered only from decision points (ChatML that replays the stored prompt + `action_id` reply); there is no JSONL-from-games export path. Dataset registration accepts `eval_ratio` (0–0.5) for train/eval split by `game_id`. Player configs and experiments can be shared as JSON packs (`cardlab.player_pack` / `cardlab.experiment_pack`): packs do not include API keys; existing player ids are reused, not overwritten; import lists providers and Ollama tags that still need to be configured on this machine.

## Game observer

- WebSocket: `WS /api/v1/games/ws/{game_id}`.
- Live: `GenericBoard` + thinking rail. Thinking seat uses `ink-obs-glow` (not a full-card pulse) and shows a live thought excerpt on the seat. The right rail is thinking above a quiet action log — do not bring back a history/thinking segmented control. The thinking panel shows legal moves, tool win-rate / hand strength, and whether parse fell back to a rule action.
- Finished games: step replay (play/pause, prev/next, speed). Current replay frame can show the same EV explain line as highlights via `GET /api/v1/games/{id}/decision-commentary` (not a board sticker; live frames skip this). Post-game **highlights** (3–5 moves from stored decision points: last play, blunder, bomb, parse fallback, endgame, high-branch — the internal `blunder` tag is `ev_loss >= BLUNDER_EV_LOSS`, a display threshold for large estimated payoff gaps, not a validated error classification) on the result dialog and observer history panel; jump seeks replay and links to `/pipeline/decisions?game_id=&decision_id=`. When `evaluator_params.best_action_id` is present, the highlight line also shows the chosen action, the highest estimated-payoff evaluated action, and their estimated payoff gap.
- Demo (run library): `POST /api/v1/system/seed-demo` → `{ experiment_id, game_id, created }`; run library navigates to the experiment detail (verdict); `/game` still uses `game_id` for observer replay.

## Database (SQLite)

Schema lives in `app/database.py`. Tables:

`experiments`, `games` (nullable `experiment_id`), `rounds`, `datasets`, `training_tasks` (nullable `experiment_id`), `prompt_templates`, `traces`, `spans`, `decision_points` (`train_usable`, `outcome`, `ev_loss`, `policy_kind`, `tool_calls`, `annotation`), `experiment_configs` (`policy_kind`: `llm` / `tool_loop` / `search` / `heuristic` / `random` / `first`).

Schema changes go through `app/migrations.py`: a numbered migration list tracked by
`PRAGMA user_version`. `_SCHEMA_SQL` builds a new database; migrations change an existing
one, so adding a column means editing both. An index over a migration-added column belongs
in the migration — `_SCHEMA_SQL` also runs against pre-migration databases. A database
newer than the running build raises `SchemaVersionError` instead of being read. Greenfield
DBs already include historically added columns in `_SCHEMA_SQL`; the migration list was empty
until the first real ALTER (`policy_kind` on decisions = migration 1; player
`policy_kind` = migration 2; decision `tool_calls` = migration 3;
decision `annotation` = migration 4; `experiment_memory` = migration 5; durable
`experiment_collect_requests` = migration 6). Migrations 7–10 add research budgets and
registered expenses, supplier cost snapshots, periodic sync plans, and cost reconciliation.
The current schema version is 10.

JSONL under `data/games/{YYYY-MM-DD}/` uses the path frozen in `games.data_file`, including across UTC midnight. The writer restores that path at startup of each game; old multi-day fragments are merged for replay. SQLite stores the index and structured decision/trace records.

`outcome` is the final team outcome for the acting seat (win, lose or null). `ev_loss` is the per-decision signal: the estimated expected payoff difference between the highest-scored candidate and the selected action under the recorded simulation conditions. `NULL` means the move was never evaluated and must not be read as 0.0 (which includes estimated ties and the degenerate single-candidate case; it does not prove optimal play). Each point also stores `train_usable_reason` (from `evaluate_train_usable`), `policy_kind` (e.g. `llm` / `heuristic`), and `evaluator_params` (rollout knobs plus, when scored, `best_action_id`, `action_values`, `candidates_evaluated`, `legal_action_count`, `truncated` for DPO export and honesty; including `opponent_kind_requested` / `opponent_kind_effective`). `GET /decision-points/stats` returns `not_usable_reason_counts` plus `evaluated_count` / `avg_ev_loss` / `blunder_count`. Export defaults to `include_thinking=false`. ChatML export writes SFT JSONL; `POST .../export-preferences` writes DPO pairs under `{data_dir}/datasets/preferences_*.jsonl` (skips rows missing `best_action_id`; default `min_ev_gap=0.05`; optional thinking only on the rejected side). `POST .../export-distill-preferences` requires matching frozen engine protocols and uniquely paired completed deals. It reuses `decision_alignment` and exports only the first action divergence after a continuously verified shared history, with valid menus/actions and student prompts. Teacher choice is a preference source, not ground truth. All exclusion counters describe student decisions.

## Decision points (SFT)

Each AI move stores state–action: hand, opponent counts, last action, phase, legal actions, chosen action, thinking, `ev_loss`, and optional `tool_calls` (compact tool-name summary from the turn). Board fields are taken from the same ``Observation`` the policy saw (`services/decision_snapshot.py`); EV scoring still uses the live ``GameState``.

EV loss is scored inline in `AIService._record_decision_point` (`DecisionEvaluator` → `core/eval/rollout.py`), while the live state still exists: a stored decision point does not carry the `ActionId` values or public information `sample_hidden_state` needs to rebuild a world. Experiment create freezes EV knobs into `protocol.scorer.evaluator` (from Settings: determinizations, max candidates, `opponent_kind`, `self_proxy`); scoring prefers that snapshot over the process default. It costs roughly 100 ms of local CPU per move and no API budget; `EV_LOSS_ENABLED=false` turns it off. Scoring never raises — an engine without hidden-state sampling, or any failure, stores `NULL` rather than failing the game.

### LLM VCR (record / replay)

`AIService` wraps the provider client when `VCR_MODE` is `record` or `replay` (see `VCR_DIR`, `VCR_CASSETTE`). Record writes `{data_dir}/vcr/{cassette}.jsonl`; stream calls are aggregated into one cassette entry. Replay never hits the network — a missing key is `VcrMissError`. Useful for CI and prompt-regression audits; not exposed in the UI.

`train_usable` (structural validity) and `max_ev_loss` (estimated payoff gap under the saved evaluator) are **separate** export filters and must stay that way: a legal move with a large estimated gap can still be a well-formed sample, and whether you want it depends on what you are training. `max_ev_loss` keeps unevaluated moves, otherwise turning it on would silently drop every decision recorded before EV scoring existed.

A rescued move (`parse_fallback`) is never training data. The flag is set by the policy when it
had to pick an action for the model, so `evaluate_train_usable` reads a structural signal rather
than sniffing the thinking text for a prefix.

## The decision protocol

The model picks an **`ActionId`** off a menu; it never describes a move. `engine.present_legal_actions()`
selects up to `MAX_PRESENTED_ACTIONS` entries round-robin across action types.
Use the engine's priority types when there are fewer slots than action types.
Dou Dizhu reserves a slot for `PASS` when it is legal and the limit is positive.
`action_menu.render_menu()` formats the selected entries, and the reply is
`{"thinking": ..., "action_id": ...}` constrained by a JSON Schema `enum` over exactly those ids.
`ActionIdParser` only validates that the id is in the legal set — there is one game-agnostic parser,
not one per phase.

Two consequences worth remembering:

- Prompt templates are versioned `v3` / `v3_reasoning` and carry `{format_instructions}`. A template
  that predates the id protocol will produce unparseable replies.
- **`parser_success` is discontinuous at this change.** The old parsers had a soft fallback that
  guessed a move and still reported success; a guess is now a failure with `parse_fallback=True`.
  The rate is more honest and lower. Do not compare `parser_success` across this boundary — rerun
  the control instead.

```
GET  /api/v1/decision-points          # page / page_size (default 10), filters include experiment_id, train_usable, max_ev_loss
GET  /api/v1/decision-points/{id}
GET  /api/v1/decision-points/stats
POST /api/v1/decision-points/export   # ChatML JSONL only; does not register a dataset
POST /api/v1/decision-points/export-preferences  # DPO JSONL (chosen vs highest estimated-payoff evaluated action); no UI
POST /api/v1/decision-points/export-distill-preferences  # teacher vs student; no UI
POST /api/v1/datasets/from-decisions  # register ChatML for the training page
```

UI: `DecisionView.vue`. Detail shows legal moves (chosen highlighted), tool win-rate, and parse fallback from the matching trace. Empty-file export does **not** appear on Training.

## Traces

```
GET /api/v1/traces            # PaginatedData; game_id / experiment_id / player_id
GET /api/v1/traces/{trace_id}
GET /api/v1/traces/metrics
```

UI: `TraceView.vue`, `TraceDetail.vue`, `TraceMetrics.vue`.

## Data page

`DataView.vue` tabs (query `?tab=`):

- **Overview** (`OverviewTab` → `StatCards`) — corpus KPIs, tokens, game-quality KPIs, wins-by-role pie. No per-model bars here.
- **AI performance** (`AIPerformanceTab`) — per-model latency P50/P95, win-rate, tokens, response time. Each chart once.
- **Datasets / storage / archive**.

`DataService.get_stats(experiment_id=...)` aggregates `games` + `rounds`.

## Training / deploy

- Create task: `POST /api/v1/training/tasks` (refuses if training extra missing). Optional `config.qlora` (4-bit NF4; needs CUDA + `bitsandbytes`, not in the poetry training group). Default remains PEFT LoRA.
- Models: `GET/DELETE /api/v1/models`, `POST .../export`, `POST .../push-ollama`, `POST .../verify`.
- Push-to-Ollama needs `LLAMA_CPP_DIR` in `.env`. Optional register-as-player after push.

## Adding a card game

1. Add `server/app/core/engine/<game_name>/` implementing `GameEngine`.
2. Override `capability` (`EngineCapability`): slots, phases, `prompt_keys`, deal-seed /
   benchmark seeds, roles, `eval_metric_ids`, `decision_schema_version`, `rules_ref`,
   optional `display_name`. Override `default_system_template(phase)` when a phase needs
   built-in copy (Dou Dizhu bidding lives in `engine/doudizhu/prompts.py`).
3. Register in `get_engine_registry()` (`dependencies.py` / engine package init).
4. `get_public_info(..., is_observer=True)` must emit `ObserverSnapshot` (`game_type`, `phase`, `round`, `current_player_id`, `players[]`, `table.slots`, `extras`).
5. Override `action_label` and `order_legal_actions` when the menu needs game-specific
   wording or ordering; `present_legal_actions` handles truncation for you.
6. Add `v3` prompt templates keyed by `capability.prompt_keys`. Parsing is shared —
   `ActionIdParser` validates against your own `LegalAction` ids, so a new game needs no parser.

Do **not** add a per-game Vue board or `game_type` branches in `GameObserverView`.

`GET /system/engines` exposes capability; experiment `protocol` is written complete at
create time as a Task document (`schema_version` currently `2`: nested `dataset` /
`solver` / `scorer` / `engine`). `solver.prompt_version` plus `solver.prompts`
(per-key `content` + `content_hash`) freeze the template bodies used at collect;
live Prompt DB edits do not change an in-flight experiment. Create accepts optional
`prompt_version` (default `v3`). Incomplete or wrong-version protocol is rejected on
collect and collect preflight (no silent migration). Decision points stay on the shared
table (JSON fields); `decision_schema_version` documents the payload contract.

Routing is by `game_type`; Service layers must not hardcode a game id beyond defaults.

## Adding an LLM provider

- If the vendor uses Chat Completions (`POST /chat/completions` + Bearer), add it to the provider list in `dependencies.py` + settings / `.env`. Do not add a new client class.
- A new `LLMClient` subclass is only for a different protocol (e.g. native Anthropic). Register it on `LLMClientFactory`.
- Player configs are created and edited in the Player configs UI (SQLite). Set
  `policy_kind` to a baseline for zero-API seats. There is no YAML seed.

Supplier reconciliation (migration 10) accepts manually entered evidence or an imported project cost CSV. `BillingReconciliationService` compares matching organization/project/currency and completed UTC periods within a saved successful snapshot. Keep crossing cost buckets intact and leave the difference unset for incomparable evidence. Exact decimal differences are API-period amount minus evidence amount. Recheck preview hashes on save. Preserve idempotency, original results and append-only review events. Default-off reconciliation policies block new controlled tasks for unresolved differences or incomparable records across all configuration versions. `resolve` documents disposition without changing amounts or waiving existing cost/freshness limits. `void` retains history. The gate uses the existing task-admission transaction. UI edits must survive polling, conflicts and close attempts. CSV records retain the file hash, column mapping and service date range. The user keeps the original file. See the read-only replay and real-invoice acceptance steps in `specs/desktop-research-workspace/billing-acceptance.md`.

## Key conventions

- Coding standards apply to the files you submit; when you edit a file, bring nearby code in that range up to the same standard (`docs/CODING_STANDARDS.md`).
- Python: annotate new/changed functions with 3.11+ syntax (`list[...]`, `X | Y`, `X | None`). Do not use `typing.List/Dict/Optional/Union`.
- Python: async for I/O. CPU-bound work via `asyncio.to_thread()`.
- Python: structlog key-value pairs; no f-strings in log calls; no `print()`.
- Python: exceptions inherit `AppError` (`app/utils/exceptions.py`).
- Python: Ruff line-length 100; mypy strict is the target for new/changed code.
- Frontend: no new `any`; narrow existing `any` in files you touch.
- Frontend: shared API errors via `src/api/client.ts` and `src/utils/error.ts`.
- Frontend: `@` → `web/src/`.
- Tests: pytest `asyncio_mode = auto`; `httpx.AsyncClient` + `ASGITransport`. Frontend: Vitest (`src/**/*.spec.ts`).
- Git: conventional commits `<type>(<scope>): <subject>`. Default branch is **`main`**. Do not create a feature branch unless the user asks.
- No cross-layer calls. No global mutable state.

## Documentation map

| Doc | Role |
|-----|------|
| `README.md` | Human getting-started (Chinese); English: `README.en.md` |
| `docs/E2E_PIPELINE.md` | Collect → train → Ollama loop + scripts |
| `docs/ARCHITECTURE.md` | Layering, events, WS, schema |
| `docs/PROJECT_STRUCTURE.md` | Directory map |
| `docs/CODING_STANDARDS.md` | Python / Vue / Git rules |
| `docs/API_DESIGN.md` | REST + WebSocket contract |
| `docs/EXAMPLES.md` | How to extend engines / providers |
| `docs/ROADMAP.md` | Agreed direction: Policy abstraction, decision-level EV loss, eval harness, RL env, priorities (not current state) |
| `docs/欢乐斗地主经典玩法规则.md` | Dou Dizhu rules reference |

Prefer this file and the code when a long-form doc disagrees.

### Research workflow contract

Experiment detail exposes hypothesis/conclusion editing, comparison and control creation at every stage. Training remains optional under Analyze. The existing notebook stores editable text; it is not a versioned evidence snapshot. Review links explicitly use `train_usable=all` so structurally invalid decisions remain visible. Control creation defaults to source seats and includes all registered configurations without preferring `lora_*`. `collect=1` opens the confirmation dialog only; one-shot `collect` and `open_control` query parameters are consumed. Only an explicit collect submission starts games. Comparison suggestions on a control include its source experiment. No database migration is required for this workflow.

### Comparison integrity and snapshots

`core/stats/comparison.py` builds the sole effective seed cohort used by comparison rows and detail delta statistics. Exclude every duplicate seed (even failed retries), incomplete outcomes and mismatched seat order; never pick a first/last row. `coverage` separates planned seeds from effective seeds and retains member game IDs and exclusion reasons. Accept only the current nested Task protocol (schema_version=2); reject other protocol formats without conversion. `protocol_review` checks frozen fields by seat and exact declared Solver paths; rules, scorer and deal-plan changes cannot be waived. The check is retrospective and descriptive, not preregistration or statistical significance. Detail without declarations uses `protocol_mismatch` to suppress unsupported conclusions.

`comparison_snapshots` is append-only through `ComparisonRepository`; schema initialization creates this independent table for both old and new databases. POST `/experiments/comparisons` recalculates on the server, saves a result with `metric_version=paired-cohort-v5`, and returns the snapshot shown by the UI. GET list is paginated; GET by ID never recomputes and has no dependency on experiments still existing. The saved JSON is a comparison record, not a full evidence/reproduction package. `ExperimentCompareView` must flag selection/declaration changes as stale, require recomparison before save, and restore `?snapshot=` without a compare request. All matrix deltas are relative to the first column; numeric maxima are not styled as winners.

Pairs navigation accepts an optional scenario, using the canonical SQL only within frozen
`coverage.members` and `computed_at`. Counts read currently retained source records; the
saved whole-run format diagnostics have different denominators and remain unchanged.
Retain a pair if either side matches. Always align full sequences before marking matching
turns, preserve gaps, and never re-pair separately filtered records. Preserve scenario with
seed/turn through decision links and the desktop query allowlist. Explicit missing positions
show an error instead of selecting another record. See `specs/desktop-research-workspace/batch-3c.md`.

Research conclusions use `research_revisions`, append-only per comparison with optimistic revision checks inside `BEGIN IMMEDIATE`. Freeze cited decision fields; source changes/deletion only affect live evidence status. Never silently overwrite a conclusion or rebase a draft after conflict. Only current nested Task protocols are accepted for comparison. The exported research report contains the comparison and selected evidence, not runnable dependencies or complete game archives.

`/research-reports/:id` reads one revision through the existing report export API. Its Vue
document is also the sole source for script-free standalone HTML; HTML and JSON use the same
loaded payload. New comparison snapshots include run hypotheses; never backfill missing
historical hypotheses from current runs. Resolve citation provenance only from frozen
`coverage.members`; carry `report_id` and `evidence` through current-source navigation and
restore the exact citation on return. HTML retains only in-document anchors, with no app
routes or remote resources. See `specs/desktop-research-workspace/batch-4a.md`.


### Research metric safeguards

Puzzle reports use `puzzle-scoring-v2`: all stored maximum-value ties count, unscored choices remain null, and summaries expose evaluated/unevaluated denominators. Empty data never renders as zero performance. Probe trials use the same decision randomness for original and perturbed inputs and separately report original-input repeat agreement. These are descriptive action diagnostics, not correctness or general robustness measures.

Saved puzzle history is read through `PuzzleService.results/result`, validated by
`core/eval/puzzle_results.py`; reading never runs policies. New records atomically publish
without replacement and freeze source summaries plus a normalized full-pack fingerprint.
Legacy v2 records without snapshots remain explicitly unrecorded. Missing, changed,
unreadable and matching current packs are distinct; never backfill historical sources.
The fingerprint checks pack content, not current database decisions or authenticity.
`PuzzleResultDocument.vue` is the single readable page/HTML source; reuse existing export
transport. Preserve `pack_id/result_id/result_page` and the decision return queries in
desktop route metadata. These test records are not published comparison conclusions.
See `specs/desktop-research-workspace/batch-4d.md`.

Formal conclusions may explicitly cite saved decision and batch tests via `research_puzzles.py`.
Reuse comparison drafts and `research_revisions`; never create another persistence path.
Preview and publication verify the frozen cohort/cutoff, source identity, evaluator settings,
full puzzle hash against reconstructed recorded history, and current pack/report consistency.
`decision_record` packs have one position and reuse source estimates. New `rollout_spread`
packs may cite up to 200 positions; their estimates are generated at extraction, not copied
from source decisions. Save the candidate ledger, completed-game scope, stable descending
spread rule/caps, effective continuation policy, and per-position decision/puzzle hashes.
Reuse `select_spread_indices` for selection and audit checks, and `recorded_puzzle` for replay.
Every selected source must pass; reject the whole citation instead of filtering it. Old or
unverified packs remain standalone. Render selection bias and within-game dependence explicitly.
Recheck the preview hash at publication; freeze at most five citations and 8 MiB of content.
Keep current file/decision status outside immutable records. Reading reports never executes
tests or replays games. Reuse `PuzzleResultDocument` with publication-specific wording.
Carry `report_id/puzzle_evidence` through test/decision navigation and desktop route metadata.
These exploratory citations do not change comparison statistics or add independent games.
See `specs/desktop-research-workspace/batch-4e.md`.
Batch citation details: `specs/desktop-research-workspace/batch-4f.md`.

SFT validation splits use `core/training/data_split.py`: group by game type and deal seed, falling back to game ID only without a seed. Save the grouping method and held-out group members in dataset filters. Do not estimate train/eval counts from game counts in the UI; the registered files determine the counts. Aggregate model win rates are descriptive across recorded roles, opponents and prompts; the sample-size flag `low_power` is not a statistical power calculation.

Direct position-test citation reuses `checked_puzzle` and `check_puzzle_scope` for discovery, preview and publication. Verify sources once per request, then check every source against each candidate cohort; never accept a batch because only its first source matches. `EvidenceCitationEntry` shares comparison selection; `PuzzleCitationPreview` shares preview, duplicate and five-test-limit behavior. `review_pack/result/hash/page` are read-only preview positions; navigation never adds citations. See `batch-3e.md`.
