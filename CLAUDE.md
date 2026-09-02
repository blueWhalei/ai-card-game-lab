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
  - `training/` — ChatML export + PEFT LoRA SFT (`sft.py`), CPU-smoke clamps, deploy/GGUF/Ollama helpers. Missing training deps refuse task creation. Status: `pending` → `exporting` → `training` → `completed` / `failed` / `cancelled`. There is no project-level `Trainer` ABC.
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
  - `WorkbenchLayout.vue` — grouped nav: Lab / Data & training / Tune (zh: 研究 / 数据与训练 / 调试). Page enter fade only (`ink-page`); do not wrap the observer shell. Layout owns the page title; list pages should not repeat an in-page subtitle. Brand logo at `/logo.png` in sidebar header. **Usage guide** (`/guide`) is header-only via `HeaderToggles` (book icon), not in the sidebar.
  - `ObserverLayout.vue` — fullscreen watch / replay.
- UI kit: `components/ui/*` (Reka UI + Ink Lab tokens in `styles/tokens.css`, motion in `styles/motion.css`). Density helpers: `KpiStrip`, `NameChips`, `CompactRecordList`, `UiTable` compact mode. Charts: ECharts.
- Experiment detail is a **stage workbench** (collect, watch, next-step primary CTA); decisions/traces/training live on Pipeline pages with `?experiment_id=`. Legacy `/experiments/:id?tab=decisions|traces|training` redirects to those pages.
- Observation uses **one** `GenericBoard` list board. Do not add `components/game/boards/<Game>Board.vue` or branch `GameObserverView` by `game_type`.

### Routes

| Path | View |
|------|------|
| `/` | `ExperimentListView` (home) |
| `/experiments/:id` | `ExperimentDetailView` (detail page; stage workbench with primary CTA) |
| `/experiments/compare` | `ExperimentCompareView` |
| `/pipeline` | redirect to `/` |
| `/game` | `GameView` (trial games — zh: 试玩对局) |
| `/game/:id` | `GameObserverView` (Observer shell) |
| `/experiment-configs` | `ExperimentConfigView` (`/ai-players` redirects here) |
| `/data` | `DataView` |
| `/decisions` | `DecisionView` |
| `/training` | `TrainingView` |
| `/prompt` | `PromptView` |
| `/traces` | `TraceView` |
| `/settings` | `SettingsView` (read-only: providers, paths, storage; preflight via `GET /api/v1/system/preflight`) |
| `/guide` | `GuideView` (usage guide: modules, flow diagrams; TOC on the right on desktop) |

Deep links: `/decisions?experiment_id=`, `/traces?experiment_id=`, `/data?experiment_id=`, `/training?experiment_id=`. Tool pages with `experiment_id` show a context bar back to the experiment detail.

## Experiments

- Table `experiments` includes `hypothesis`, `conclusion`, `tags` (JSON array), plus existing `notes` and frozen `protocol`.
- `games.experiment_id` is nullable (trial games on `/game` stay outside experiments).
- Creating an experiment does **not** start games (avoids accidental API spend). Collect from the detail page.
- Player count is validated against the engine `min` / `max` from `GET /api/v1/system/engines`.
- Detail page: `ExperimentDetailContextBar` (`next_step` primary action), `ExperimentValidationStrip` (control progress), games list, optional results strip + players tab after first finished game; **archive** dialog (notebook, protocol, validation, clone/manifest). Collect / pause, watch, register-and-train, control wizard, compare via primary action or ⋯ menu.
- `collect_mode`: `free` (random seeds) or `benchmark` (fixed `deal_seeds` from `BENCHMARK_DEAL_SEEDS`, up to 50 games).
- Detail tabs: **games** / **players** only (`?tab=players`); deep analysis uses Pipeline deep links above.
- Summary / compare expose eval metrics: role win rates, parser rate, train_usable, P50/P95 latency (from `rounds`), tokens/game, status counts, per-seat as-landlord win rate (needs `metadata.landlord_id`), plus `credibility` (decisive_n / CI width / low_power). Collect CTA uses `GET /api/v1/system/preflight` (seat providers); Settings shows the same checks.
- `GET /experiments/{id}` adds computed `timeline`, `validation` (control runs + `control_progress` + `validation_ready`), and `next_step` (`collect_control` → control experiment collect).
- Completed training tasks for the experiment appear on `/training?experiment_id=`; model repo can register an Ollama tag as a player config.

Main HTTP:

```
GET/POST /api/v1/experiments
PATCH    /api/v1/experiments/{id}
POST     /api/v1/experiments/{id}/clone
GET      /api/v1/experiments/compare?ids=a,b
GET      /api/v1/experiments/{id}
POST     /api/v1/experiments/{id}/collect
GET      /api/v1/system/benchmark-seeds
GET      /api/v1/system/preflight
```

Decision export, trace list, `GET /api/v1/data/stats`, and `POST /api/v1/datasets/from-decisions` accept `experiment_id`. Dataset registration accepts `eval_ratio` (0–0.5) for train/eval split by `game_id`.

## Game observer

- WebSocket: `WS /api/v1/games/ws/{game_id}`.
- Live: `GenericBoard` + action history / thinking panel. Thinking seat uses `ink-obs-glow` (not a full-card pulse).
- Finished games: step replay (play/pause, prev/next, speed).
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

UI: `DecisionView.vue`. Empty-file export does **not** appear on Training.

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

- Create task: `POST /api/v1/training/tasks` (refuses if training extra missing).
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
