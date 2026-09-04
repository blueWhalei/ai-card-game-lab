---
description: Agent guide for CardLab
alwaysApply: true
---

# CLAUDE.md

Guidance for agents working in this repository.

## Project overview

CardLab (repo: `ai-card-game-lab`) is a local research tool for AI-vs-AI card games: run games, observe decisions, collect data, and fine-tune small models.

The primary product object is an **experiment** (run): a fixed set of player configs plus a target game count. Collect, observe, register-and-train, open a control experiment, and compare runs from the experiment detail page. Trial games (no experiment; zh: 试玩对局) still exist on `/game`.

Monorepo:

| Workspace | Stack |
|-----------|--------|
| `server/` | Python 3.11+ / FastAPI / Poetry / aiosqlite |
| `web/` | Vue 3 + TypeScript / Vite / Tailwind v4 / Reka UI |

Default frontend port is `5173` (proxies `/api` and `/api/v1/games/ws` to `localhost:8000`).

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
poetry run pytest
poetry run pytest tests/test_api/test_system.py
poetry run pytest -k "test_health"
poetry run ruff check .
poetry run ruff format .
poetry run mypy app/
```

Training extras (PEFT LoRA): `poetry install --with training`.

### Frontend (`web/`)

```bash
cd web
npm install
npm run dev
npm run build
npm run lint
npm run format
npm run type-check
npm test
```

## Architecture

Strict one-way backend dependency:

```
API (app/api/) → Service (app/services/) → Repository (app/repositories/) → database
                                         → Core (app/core/)
```

- **API** — routes, validation, serialization. Never call Core or Repository.
- **Service** — orchestration. Singletons do not hold DB connections; background work opens its own connection.
- **Repository** — SQLite via aiosqlite.
- **Core** — framework-independent domain logic:
  - `engine/` — `GameEngine` ABC + `EngineCapability` + `GameEngineRegistry`. Engines are stateless; state is `GameState`. First engine: Dou Dizhu (`doudizhu`).
  - `engine/observer_types.py` — `ObserverSnapshot` protocol for the observer UI.
  - `ai/` — `LLMClient` ABC + `LLMClientFactory`. Two implementations: `OpenAICompatibleClient` (OpenAI, DashScope, DeepSeek, Kimi, Zhipu, Yi, Baichuan, MiniMax) and `OllamaClient`. Wired in `dependencies.py`. Streaming uses `stream_options: {"include_usage": true}`; final `StreamChunk` may carry `usage`.
  - `collector/` — JSONL writer.
  - `training/` — ChatML export + PEFT LoRA SFT (`sft.py`), optional 4-bit QLoRA, CPU-smoke clamps, deploy/GGUF/Ollama helpers. Missing training deps refuse task creation. Status: `pending` → `exporting` → `training` → `completed` / `failed` / `cancelled`. There is no project-level `Trainer` ABC.
  - `events/` — in-process `EventBus` + game lifecycle events.
- **WebSocket** (`app/websocket/`) — `ConnectionManager` broadcasts per-game events; `handlers.py` is the WS endpoint.
- **Schemas** (`app/schemas/`) — Pydantic request/response models. Shared `ApiResponse` / `PaginatedData`.
- **Config** — `app/config.py` (`pydantic-settings`) from env / project-root `.env`. Player configs live in SQLite and are created in the Player configs UI (`/experiment-configs`); there is no YAML seed.

## Frontend

- Vue 3 `<script setup lang="ts">`, Pinia, Vue Router, vue-i18n (`zh-CN` + `en`). New user-facing copy goes through i18n.
- `src/api/` — typed Axios client (`client.ts` normalizes errors). Domain modules: `experimentApi`, `experimentConfigApi`, `gameApi`, `dataApi`, `decision`, `traces`, `trainingApi`, `prompts`, `systemApi`, `archive`.
- `src/stores/` — `useGameStore`, `useDataStore`, `useTrainingStore`.
- `src/composables/` — `useWebSocket`, `useGameWebSocket` (observer), `usePagination`, `useTweenNumber`, `useFieldWidth`, `useTheme`, `useLocale`.
- Dual shells:
  - `WorkbenchLayout.vue` — five destinations: Experiments / Players / Trial games / Analyze / Settings (zh: 实验 / 选手 / 试玩 / 分析 / 设置). Analyze is a hub (`/pipeline/{data,decisions,training,traces}`); old `/data` `/decisions` `/training` `/traces` redirect and keep query. Prompts stay at `/prompt`, linked from Settings. Route swap is immediate (no page `Transition`; it raced with overlay unmount). Do not wrap the observer shell. Layout owns the page title; list pages should not repeat an in-page subtitle. Brand logo at `/logo.png` in sidebar header. **Usage guide** (`/guide`) is header-only via `HeaderToggles` (book icon), not in the sidebar.
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
- Experiment detail is a **five-act stage**: `resolveStageId()` (`utils/experimentStage.ts`) picks
  one of `empty` / `collecting` / `harvest` / `control` / `verdict`, and `ExperimentStage.vue`
  renders exactly one act — a single claim sentence plus a single action (`StageAction.vue`,
  or `StageVerdict.vue` for the verdict). Do **not** reintroduce stacked strips or a games/players
  segmented control; the games list and player table are quiet sections under
  `ExperimentTimeline.vue`. Decisions/traces/training live on Pipeline pages with
  `?experiment_id=`. Legacy `/experiments/:id?tab=decisions|traces|training` redirects there.
- A blocking preflight check **replaces** the act's claim and action rather than sitting in a
  banner above a button that only warns. Only `severity: warn` renders as a notice.
- Observation uses **one** `GenericBoard` list board. Do not add `components/game/boards/<Game>Board.vue` or branch `GameObserverView` by `game_type`.

### Routes

| Path | View |
|------|------|
| `/` | `ExperimentListView` (home; first-run checklist until provider + players + experiment) |
| `/experiments/:id` | `ExperimentDetailView` (detail page; stage workbench with primary CTA) |
| `/experiments/compare` | `ExperimentCompareView` |
| `/pipeline` | `PipelineView` (Analyze hub; redirects to `/pipeline/data`) |
| `/pipeline/data` | `DataView` |
| `/pipeline/decisions` | `DecisionView` |
| `/pipeline/training` | `TrainingView` |
| `/pipeline/traces` | `TraceView` |
| `/game` | `GameView` (trial games — zh: 试玩对局) |
| `/game/:id` | `GameObserverView` (Observer shell) |
| `/experiment-configs` | `ExperimentConfigView` (`/ai-players` redirects here) |
| `/prompt` | `PromptView` (linked from Settings; not in the sidebar) |
| `/settings` | `SettingsView` (read-only: providers, paths, storage; preflight via `GET /api/v1/system/preflight`) |
| `/guide` | `GuideView` (usage guide: modules, flow diagrams; TOC on the right on desktop) |

Legacy `/data`, `/decisions`, `/training`, `/traces` redirect to the matching `/pipeline/…` path and keep the query. Deep links (`?experiment_id=`, `?game_id=&decision_id=`) still work. The Analyze hub owns the experiment context bar.

## Experiments

- Table `experiments` includes `hypothesis`, `conclusion`, `tags` (JSON array), plus existing `notes` and frozen `protocol`.
- `games.experiment_id` is nullable (trial games on `/game` stay outside experiments).
- Creating an experiment does **not** start games (avoids accidental API spend). Start the experiment from the detail page.
- Home (`/`): first-run checklist (configured provider → enough player configs → an experiment) until complete; **Load demo** remains a skip path. Experiment list can **import** a JSON pack; detail ⋯ **export** is the same format (legacy client manifests still import).
- Player count is validated against the engine `min` / `max` from `GET /api/v1/system/engines`.
- Detail page acts, in the order `resolveStageId()` checks them: `empty` (no games — Start experiment, and say it costs API usage), `collecting` (progress number + watch), `harvest` (trainable-decision count + Start training, or review exclusions when `next_step.id=review_decisions`), `control` (explain same-deal validation; register the `lora_*` player first when none exists; Start control experiment), `verdict` (`StageVerdict`). Identity bar (back / name / status / ⋯) and the **archive** dialog (notebook, protocol, validation, clone/manifest) stay on every act. The ⋯ menu carries the experiment-scoped Pipeline entries (decisions / data / training / traces); acts only link out when that *is* the next step (e.g. `review_decisions`), so pruning an act must not prune a deep link. Home list keeps **Compare several experiments**.
- The verdict act shows: one claim sentence from `delta.verdict_key`, the Δ number, a support line (paired n + CI), and an evidence line that turns "not enough" into a number of games to run. `can_conclude=false` renders the claim and number through `--ink-evidence-weak` (lighter, not bold) — confidence is legible without reading the text. Scenario subscores are a `ExperimentScenarioBars` small-multiples row that only annotates the one notable gap, not four equal KPI cells.
- Δ cells have a `?` (`MetricHint`) linking to `/guide#metrics`. Formulas live in `metricHint.*` i18n and `guide.sections.metrics`. Changing an eval formula or verdict copy requires updating both. Δ is **not** colored good/bad.
- `collect_mode`: `free` (random seeds) or `benchmark` (fixed `deal_seeds` from `BENCHMARK_DEAL_SEEDS`, up to 50 games).
- Summary / compare expose eval metrics: role win rates, parser rate, train_usable, P50/P95 latency (from `rounds`), tokens/game, status counts, per-seat as-landlord win rate (needs `metadata.landlord_id`), plus `credibility` (decisive_n / CI width / low_power) and `scenario_scores` (bidding / playing / endgame / bomb: train_usable + parser). Collect CTA uses `GET /api/v1/system/preflight` (seat providers); Settings shows the same checks. UI copy comes from `preflight.*` by check `id` (not the backend `message`).
- `GET /experiments/{id}` adds computed `timeline`, `validation` (control runs + `control_progress` + `validation_ready`), `next_step` (`open_control` after training completes with no control yet; `collect_control` → control experiment collect; `review` + `action=stay` when a control is ready — stay on the detail verdict, do not jump to compare), and `delta` (vs source or first control: landlord win-rate Δ, paired n, CI, `can_conclude` / `inconclusive_reason`, `verdict_key`, plus per-scenario train/parser Δ). New decisions store `game_phase=endgame` when any remaining hand has ≤8 cards.
- `verdict_key` (`stronger` / `weaker` / `even` / `peer_pending` / `no_data`, from `_verdict_key()`) is the plain-language claim the UI renders as `stage.verdict.<key>`. It is computed server-side on purpose: an eval-formula change and its wording live in one place. `VERDICT_EVEN_THRESHOLD` decides when a gap is a tie. `verdictKeyOf()` mirrors it for payloads that predate the field.
- Completed training tasks for the experiment appear on `/training?experiment_id=`; model repo can register an Ollama tag as a player config.

Main HTTP:

```
GET/POST /api/v1/experiments
PATCH    /api/v1/experiments/{id}
POST     /api/v1/experiments/{id}/clone
GET      /api/v1/experiments/compare?ids=a,b
GET      /api/v1/experiments/{id}
GET      /api/v1/experiments/{id}/export
POST     /api/v1/experiments/import
POST     /api/v1/experiments/{id}/collect
GET      /api/v1/system/benchmark-seeds
GET      /api/v1/system/preflight
```

Decision export, trace list, `GET /api/v1/data/stats`, and `POST /api/v1/datasets/from-decisions` accept `experiment_id`. Dataset registration accepts `eval_ratio` (0–0.5) for train/eval split by `game_id`. Player configs and experiments can be shared as JSON packs (`cardlab.player_pack` / `cardlab.experiment_pack`): secrets are stripped; existing player ids are reused, not overwritten; import lists unconfigured providers and Ollama tags.

## Game observer

- WebSocket: `WS /api/v1/games/ws/{game_id}`.
- Live: `GenericBoard` + thinking rail. Thinking seat uses `ink-obs-glow` (not a full-card pulse) and shows a live thought excerpt on the seat. The right rail is thinking above a quiet action log — do not bring back a history/thinking segmented control. The thinking panel shows legal moves, tool win-rate / hand strength, and whether parse fell back to a rule action.
- Finished games: step replay (play/pause, prev/next, speed). Post-game **highlights** (3–5 moves from stored decision points: last play, bomb, parse fallback, endgame, high-branch) on the result dialog and observer history panel; jump seeks replay and links to `/decisions?game_id=&decision_id=`.
- Demo game (no experiment): homepage “load demo” → `POST /api/v1/system/seed-demo`.

## Database (SQLite)

Schema lives in `app/database.py`. Tables:

`experiments`, `games` (nullable `experiment_id`), `rounds`, `datasets`, `training_tasks` (nullable `experiment_id`), `prompt_templates`, `traces`, `spans`, `decision_points` (`train_usable`, `quality_score`), `experiment_configs`.

JSONL under `data/games/{YYYY-MM-DD}/` is the full archive; SQLite is the index.

`quality_score` is an **end-game outcome proxy** (win 0.8 / lose 0.3 / draw 0.5), not move quality. SFT filtering uses `train_usable`. Each point also stores `train_usable_reason` (from `evaluate_train_usable`); `GET /decision-points/stats` returns `not_usable_reason_counts`. Export defaults to `include_thinking=false`.

## Decision points (SFT)

Each AI move stores state–action: hand, opponent counts, last action, phase, legal actions, chosen action, thinking.

```
GET  /api/v1/decision-points          # page / page_size (default 10), filters include experiment_id, train_usable
GET  /api/v1/decision-points/{id}
GET  /api/v1/decision-points/stats
POST /api/v1/decision-points/export   # writes JSONL only; does not register a dataset
POST /api/v1/datasets/from-decisions  # register ChatML for the training page
```

UI: `DecisionView.vue`. Detail shows legal moves (chosen highlighted), tool win-rate, and parse fallback from the matching trace. Empty-file export does **not** appear on Training.

## Traces

```
GET /api/v1/traces            # PaginatedData; game_id / experiment_id / player_id
GET /api/v1/traces/{trace_id}
GET /api/v1/traces/metrics
GET /api/v1/traces/compare
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
   benchmark seeds, roles, `eval_metric_ids`, `decision_schema_version`, `rules_ref`.
3. Register in `get_engine_registry()` (`dependencies.py` / engine package init).
4. `get_public_info(..., is_observer=True)` must emit `ObserverSnapshot` (`game_type`, `phase`, `round`, `current_player_id`, `players[]`, `table.slots`, `extras`).
5. Implement `format_legal_actions_for_prompt` when action listing is game-specific.
6. Add prompt templates keyed by `capability.prompt_keys` (and optional parsers).

Do **not** add a per-game Vue board or `game_type` branches in `GameObserverView`.

`GET /system/engines` exposes capability; experiment `protocol` is written complete at
create time (`schema_version` currently `1`). Incomplete protocol is rejected on collect
(no silent migration). Decision points stay on the shared table (JSON fields);
`decision_schema_version` documents the payload contract.

Routing is by `game_type`; Service layers must not hardcode a game id beyond defaults.

## Adding an LLM provider

- If the vendor is OpenAI-compatible (`POST /chat/completions` + Bearer), add it to the provider list in `dependencies.py` + settings / `.env`. Do not add a new client class.
- A new `LLMClient` subclass is only for a non-compatible protocol (e.g. native Anthropic). Register it on `LLMClientFactory`.
- Player configs are created and edited in the Player configs UI (SQLite). There is no YAML seed.

## Key conventions

- Coding standards apply to **new and touched** code; fix legacy in the same range when you see it (`docs/CODING_STANDARDS.md`).
- Python: annotate new/changed functions with 3.11+ syntax (`list[...]`, `X | Y`, `X | None`). Do not use `typing.List/Dict/Optional/Union`.
- Python: async for I/O. CPU-bound work via `asyncio.to_thread()`.
- Python: structlog key-value pairs; no f-strings in log calls; no `print()`.
- Python: exceptions inherit `AppError` (`app/utils/exceptions.py`).
- Python: Ruff line-length 100; mypy strict is the target for new/changed code.
- Frontend: no new `any`; narrow legacy `any` in files you touch.
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
| `docs/欢乐斗地主经典玩法规则.md` | Dou Dizhu rules reference |

Prefer this file and the code when a long-form doc disagrees.
