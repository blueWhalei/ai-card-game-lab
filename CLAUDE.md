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
poetry run python -m app.mcp   # stdio MCP (Cursor); logs on stderr
poetry run pytest
poetry run pytest tests/test_api/test_system.py
poetry run pytest -k "test_health"
poetry run ruff check .
poetry run ruff format .
poetry run mypy app/
```

Training extras (PEFT LoRA): `poetry install --with training`.

CI (`.github/workflows/ci.yml`): `poetry run pytest` + `poetry run ruff check .` (full tree; format/mypy are local-only for now).

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

CI: `npm run lint:ci` → `npm test` → `npm run build` (build already runs `type-check`).
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
  - `ai/` — `LLMClient` ABC + `LLMClientFactory`. Two implementations: `OpenAICompatibleClient` (OpenAI, DashScope, DeepSeek, Kimi, Zhipu, Yi, Baichuan, MiniMax) and `OllamaClient`. Wired in `dependencies.py`. Streaming uses `stream_options: {"include_usage": true}`; final `StreamChunk` may carry `usage`. Clients accept `response_format` and degrade (drop `stream_options`, then `response_format`) when a provider rejects it with 4xx; `OllamaClient` translates it to Ollama's `format`. Optional **VCR** wrapper (`core/ai/vcr.py`): `VCR_MODE=record|replay` stores/replays chat calls as JSONL under `data/vcr/` (match key = SHA-256 of provider + messages + model/sampling/`response_format`); `replay` miss raises `VcrMissError` (no silent live call). Default `off`.
  - `policy/` — `Policy` ABC: an async **event stream** (`ThinkingDelta` / `ToolCall` / `ToolResult` / `LlmRequest` / `LlmUsage` / `ActionChosen`) ending in exactly one `ActionChosen`. `LLMPolicy` owns everything about asking a model (prompt assembly, tools, retries, timeout, streaming fallback, parsing); `RulePolicy` / `RandomPolicy` are the non-LLM baselines. A `Budget` caps LLM and tool calls; `PolicyContext` injects `EngineAdvisor`, `PromptSource`, and the rng.
  - `eval/` — `rollout.py` scores candidate actions by determinized rollouts with common random numbers. Experiment-level **Scorer** plugins (`build_scorer_registry(game_type=…)`) cover every Dou Dizhu `eval_metric_id` (`train_usable`, `parser_success`, `latency_p50_p95`, `role:landlord`, `ev_loss`); `ExperimentService` overlays results onto summary from `protocol.scorer.eval_metric_ids`. **Puzzle packs** (`puzzle.py` / `replay.py` / `perturb.py` + `PuzzleService`): extract high-spread decisions into `{data_dir}/puzzles/{pack_id}/`, score baselines offline, and **probe** consistency under legal-action / hand-card order shuffles (`POST .../probe`). No UI in Step 4.
  - `collector/` — JSONL writer.
  - `training/` — ChatML export + PEFT LoRA SFT (`sft.py`), optional 4-bit QLoRA, CPU-smoke clamps, deploy/GGUF/Ollama helpers. **Preference (DPO) export** (`preference.py` + `DecisionService.export_preferences`): chosen = rollout `best_action_id`, rejected = model `action_id`; gold labels live in `evaluator_params` at score time (no new columns). Missing training deps refuse task creation. Status: `pending` → `exporting` → `training` → `completed` / `failed` / `cancelled`. There is no project-level `Trainer` ABC.
  - `events/` — in-process `EventBus` + game lifecycle events.
  - `env/` — duck-typed PettingZoo-style **AEC** wrapper (`CardLabAECEnv`): `reset` / `agent_iter` / `last` / `step(index)`; non-learner seats use an injected baseline `ActionSelector` (default heuristic). No hard `pettingzoo` dependency. Reward from `engine.terminal_rewards()`.
- **WebSocket** (`app/websocket/`) — `ConnectionManager` broadcasts per-game events; `handlers.py` is the WS endpoint.
- **MCP** (`app/mcp/`) — stdio Model Context Protocol server (`python -m app.mcp`, official `mcp` 2.x `MCPServer`). Read-only tools call Services directly: `list_experiments`, `get_experiment` (games off by default), `list_decision_points`, `get_decision_stats`. Logs go to stderr. Cursor example:

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
- **Config** — `app/config.py` (`pydantic-settings`) from env / project-root `.env`. Player configs live in SQLite and are created in the Player configs UI (`/experiment-configs`); there is no YAML seed.

## Frontend

- Vue 3 `<script setup lang="ts">`, Pinia, Vue Router, vue-i18n (`zh-CN` + `en`). New user-facing copy goes through i18n.
- `src/api/` — typed Axios client (`client.ts` normalizes errors). Domain modules: `experimentApi`, `experimentConfigApi`, `gameApi`, `dataApi`, `decision`, `traces`, `trainingApi`, `prompts`, `systemApi`, `archive`.
- `src/stores/` — `useGameStore`, `useDataStore`, `useTrainingStore`.
- `src/composables/` — `useWebSocket`, `useGameWebSocket` (observer), `usePagination`, `useTweenNumber`, `useFieldWidth`, `useTheme`, `useLocale`.
- Dual shells:
  - `WorkbenchLayout.vue` — five destinations: Experiments / Players / Trial games / Analyze / Settings (zh: 实验 / 选手 / 试玩 / 分析 / 设置). Analyze is a hub (`/pipeline/{data,decisions,training,traces}`). Prompts stay at `/prompt`, linked from Settings. Route swap is immediate (no page `Transition`; it raced with overlay unmount). Do not wrap the observer shell. Layout owns the page title; list pages should not repeat an in-page subtitle. Brand logo at `/logo.png` in sidebar header. **Usage guide** (`/guide`) is header-only via `HeaderToggles` (book icon), not in the sidebar.
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
  or `StageVerdict.vue` for the verdict). On verdict, **Generate conclusion draft** calls
  `POST /api/v1/experiments/{id}/conclusion-draft` (template text from `core/research/conclusion_draft.py`;
  no LLM); the user edits and confirms via `PATCH` `conclusion`. Do **not** reintroduce stacked strips or a games/players
  segmented control; the games list and player table are quiet sections under
  `ExperimentTimeline.vue`. A `collect_mode=benchmark` run also shows
  `ExperimentBenchmarkReport` between the phase and the timeline (this-run landlord WR,
  parse, trainable, P50, tokens/game, seed coverage) — not a sixth phase and not a
  second primary CTA. Decisions/traces/training live on Pipeline pages with
  `?experiment_id=`.
- A blocking preflight check **replaces** that phase's status line and action rather than sitting in a
  banner above a button that only warns. Only `severity: warn` renders as a notice.
- Observation uses **one** `GenericBoard` seat grid (center table + surround seats). Do not add `components/game/boards/<Game>Board.vue` or branch `GameObserverView` by `game_type`.

### Routes

| Path | View |
|------|------|
| `/` | `ExperimentListView` (home; first-run checklist until provider + players + experiment) |
| `/experiments/:id` | `ExperimentDetailView` (detail page; stage workbench with primary CTA) |
| `/experiments/compare` | `ExperimentCompareView` |
| `/pipeline` | `PipelineView` (Analyze hub; opens `/pipeline/data`) |
| `/pipeline/data` | `DataView` |
| `/pipeline/decisions` | `DecisionView` |
| `/pipeline/training` | `TrainingView` |
| `/pipeline/traces` | `TraceView` |
| `/game` | `GameView` (trial games — zh: 试玩对局) |
| `/game/:id` | `GameObserverView` (Observer shell) |
| `/experiment-configs` | `ExperimentConfigView` |
| `/prompt` | `PromptView` (linked from Settings; not in the sidebar) |
| `/settings` | `SettingsView` (read-only: providers, paths, storage; preflight via `GET /api/v1/system/preflight`) |
| `/guide` | `GuideView` (usage guide: modules, flow diagrams; TOC on the right on desktop) |

Deep links (`?experiment_id=`, `?game_id=&decision_id=`) keep the query. The Analyze hub owns the experiment context bar.

## Experiments

- Table `experiments` includes `hypothesis`, `conclusion`, `tags` (JSON array), plus existing `notes` and frozen `protocol`.
- `games.experiment_id` is nullable (trial games on `/game` stay outside experiments).
- Creating an experiment does **not** start games (avoids accidental API spend). Start the experiment from the detail page.
- Home (`/`): first-run checklist (configured provider → enough player configs → an experiment) until complete; **Load demo** is a skip path on the checklist/empty state (not a permanent toolbar button). List rows are scannable experiment objects (status sentence + next step), not a seven-column table. Import / compare live in a secondary menu. Detail ⋯ **export** shares the experiment-pack format.
- `GET /experiments` includes `next_step` and a compact list `delta` (no `scenario_diffs`; keeps `this_decisive_n` / `peer_decisive_n` for statistical-power copy) so the home list can resolve harvest / control / verdict without N+1 detail fetches.
- Player count is validated against the engine `min` / `max` from `GET /api/v1/system/engines`.
- Detail page phases, in the order `resolveStageId()` checks them: `empty` (no games — Start experiment, and say it costs API usage), `collecting` (progress number + watch), `harvest` (trainable-decision count + Start training, or review exclusions when `next_step.id=review_decisions`), `control` (explain same-deal validation; register the `lora_*` player first when none exists; Start control experiment), `verdict` (`StageVerdict`). Identity bar (back / name / status / ⋯) and the **archive** dialog (notebook, protocol, validation, clone/manifest) stay on every phase. The ⋯ menu carries the experiment-scoped Pipeline entries (decisions / data / training / traces); a phase only links out when that *is* the next step (e.g. `review_decisions`), so removing a phase block must not prune a deep link. Home list keeps **Compare several experiments**.
- The verdict phase shows: when `can_conclude`, one conclusion sentence from `delta.verdict_key` plus the Δ number; when not, the **headline is the evidence line** (`stage.evidence.*`) and Δ is a muted footnote — never a causal claim as the title. A support line (paired n + CI) stays under the number. Scenario subscores are a `ExperimentScenarioBars` small-multiples row that only annotates the one notable gap when the claim is strong enough; Δ is **not** colored good/bad.
- Progress UI never shows an uncapped ratio like `14/10`. Use `formatExperimentProgress(finished, target)` (`stage.progressRatio` / `progressWithExtra`): display is capped at the target (`5/5 · 多跑了 9 局` / `5/5 · 9 beyond the target`). Collect may still finish more games than `target_games` on the backend.
- Δ cells have a `?` (`MetricHint`) linking to `/guide#metrics`. Formulas live in `metricHint.*` i18n and `guide.sections.metrics`. Changing an eval formula or verdict copy requires updating both. Δ is **not** colored good/bad.
- `collect_mode`: `free` (random seeds) or `benchmark` (fixed `deal_seeds` from `BENCHMARK_DEAL_SEEDS`, up to 50 games). Creating a benchmark run in the UI defaults `target_games` to the engine `benchmark_seed_count`. Collect must not go past the declared seed list (`ExperimentValidationError`); extra random seeds are not appended.
- Summary / compare expose eval metrics: role win rates, parser rate, train_usable, P50/P95 latency (from `rounds`), tokens/game, status counts, per-seat as-landlord win rate (needs `metadata.landlord_id`), plus `credibility` (decisive_n / CI width / low_power) and `scenario_scores` (bidding / playing / endgame / bomb: train_usable + parser). Collect CTA uses `GET /api/v1/system/preflight` (seat providers); Settings shows the same checks as a read-only machine-status page (keys stay in project-root `.env`). UI copy comes from `preflight.*` by check `id` (not the backend `message`). Layout title for `/pipeline/*` is always `nav.analyze`. Experiment detail owns one identity bar with `HeaderToggles` (WorkbenchLayout skips its desktop toggles strip there). Collect confirms inline with a batch stepper; while `collecting`, Stop games is a ghost secondary on the stage and also in the ⋯ menu — not a second primary CTA. Player configs are a card roster (win rate is not colored good/bad).
- `GET /experiments/{id}` adds computed `timeline`, `validation` (control runs + `control_progress` + `validation_ready`), `next_step` (`open_control` after training completes with no control yet; `collect_control` → control experiment collect; `review` + `action=stay` when a control is ready — stay on the detail verdict, do not jump to compare), `delta` (vs source or first control: landlord win-rate Δ, paired n, CI, `can_conclude` / `inconclusive_reason`, `verdict_key`, plus per-scenario train/parser Δ), and `benchmark` (`null` unless `collect_mode=benchmark`: seed coverage of the declared `deal_seeds`). New decisions store `game_phase=endgame` when any remaining hand has ≤8 cards.
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
- Finished games: step replay (play/pause, prev/next, speed). Post-game **highlights** (3–5 moves from stored decision points: last play, blunder, bomb, parse fallback, endgame, high-branch — a `blunder` is `ev_loss >= BLUNDER_EV_LOSS`, and it outranks the others because it is the only reason derived from what a move was worth rather than what it looked like) on the result dialog and observer history panel; jump seeks replay and links to `/pipeline/decisions?game_id=&decision_id=`.
- Demo game (no experiment): homepage “load demo” → `POST /api/v1/system/seed-demo`.

## Database (SQLite)

Schema lives in `app/database.py`. Tables:

`experiments`, `games` (nullable `experiment_id`), `rounds`, `datasets`, `training_tasks` (nullable `experiment_id`), `prompt_templates`, `traces`, `spans`, `decision_points` (`train_usable`, `quality_score`, `ev_loss`), `experiment_configs`.

Schema changes go through `app/migrations.py`: a numbered migration list tracked by
`PRAGMA user_version`. `_SCHEMA_SQL` builds a new database; migrations change an existing
one, so adding a column means editing both. An index over a migration-added column belongs
in the migration — `_SCHEMA_SQL` also runs against pre-migration databases. A database
newer than the running build raises `SchemaVersionError` instead of being read.

JSONL under `data/games/{YYYY-MM-DD}/` is the full archive; SQLite is the index.

`quality_score` is an **end-game outcome proxy** (win 0.8 / lose 0.3 / draw 0.5), not move quality — one number shared by every decision in a game. `ev_loss` is the per-decision signal: value given up versus the best candidate the rollout evaluator scored. `NULL` means the move was never evaluated and must not be read as 0.0 (which means it was the best candidate). Each point also stores `train_usable_reason` (from `evaluate_train_usable`) and `evaluator_params` (rollout knobs plus, when scored, `best_action_id` and `action_values` for DPO export); `GET /decision-points/stats` returns `not_usable_reason_counts` plus `evaluated_count` / `avg_ev_loss` / `blunder_count`. Export defaults to `include_thinking=false`. ChatML export writes SFT JSONL; `POST .../export-preferences` writes DPO pairs under `{data_dir}/datasets/preferences_*.jsonl` (skips rows missing `best_action_id`; default `min_ev_gap=0.05`; optional thinking only on the rejected side).

## Decision points (SFT)

Each AI move stores state–action: hand, opponent counts, last action, phase, legal actions, chosen action, thinking, and `ev_loss`.

EV loss is scored inline in `AIService._record_decision_point` (`DecisionEvaluator` → `core/eval/rollout.py`), while the live state still exists: a stored decision point does not carry the `ActionId` values or public information `sample_hidden_state` needs to rebuild a world. It costs roughly 100 ms of local CPU per move and no API budget; `EV_LOSS_ENABLED=false` turns it off. Scoring never raises — an engine without hidden-state sampling, or any failure, stores `NULL` rather than failing the game.

### LLM VCR (record / replay)

`AIService` wraps the provider client when `VCR_MODE` is `record` or `replay` (see `VCR_DIR`, `VCR_CASSETTE`). Record writes `{data_dir}/vcr/{cassette}.jsonl`; stream calls are aggregated into one cassette entry. Replay never hits the network — a missing key is `VcrMissError`. Useful for CI and prompt-regression audits; not exposed in the UI.

`train_usable` (structural validity) and `max_ev_loss` (move quality) are **separate** export filters and must stay that way: a legal but weak move is still a well-formed sample, and whether you want it depends on what you are training. `max_ev_loss` keeps unevaluated moves, otherwise turning it on would silently drop every decision recorded before EV scoring existed.

A rescued move (`parse_fallback`) is never training data. The flag is set by the policy when it
had to pick an action for the model, so `evaluate_train_usable` reads a structural signal rather
than sniffing the thinking text for a prefix.

## The decision protocol

The model picks an **`ActionId`** off a menu; it never describes a move. `engine.present_legal_actions()`
renders the menu (round-robin across action types, capped at `MAX_PRESENTED_ACTIONS`, so truncation
can never hide `PASS`), `action_menu.render_menu()` formats it, and the reply is
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
POST /api/v1/decision-points/export-preferences  # DPO JSONL (model vs EV-best); no UI
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
5. Override `action_label` and `order_legal_actions` when the menu needs game-specific
   wording or ordering; `present_legal_actions` handles truncation for you.
6. Add `v3` prompt templates keyed by `capability.prompt_keys`. Parsing is shared —
   `ActionIdParser` validates against your own `LegalAction` ids, so a new game needs no parser.

Do **not** add a per-game Vue board or `game_type` branches in `GameObserverView`.

`GET /system/engines` exposes capability; experiment `protocol` is written complete at
create time as a Task document (`schema_version` currently `2`: nested `dataset` /
`solver` / `scorer` / `engine`). Incomplete or wrong-version protocol is rejected on
collect and collect preflight (no silent migration). Decision points stay on the shared
table (JSON fields); `decision_schema_version` documents the payload contract.

Routing is by `game_type`; Service layers must not hardcode a game id beyond defaults.

## Adding an LLM provider

- If the vendor uses Chat Completions (`POST /chat/completions` + Bearer), add it to the provider list in `dependencies.py` + settings / `.env`. Do not add a new client class.
- A new `LLMClient` subclass is only for a different protocol (e.g. native Anthropic). Register it on `LLMClientFactory`.
- Player configs are created and edited in the Player configs UI (SQLite). There is no YAML seed.

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
