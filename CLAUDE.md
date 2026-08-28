---
description: 
alwaysApply: true
---

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI Card Game Lab (AI卡牌游戏实验室) — a platform for running AI-vs-AI card games, collecting gameplay data, and fine-tuning LLMs. The backend orchestrates game engines and LLM providers; the frontend provides real-time game observation via WebSocket.

## Commands

### Backend (server/)

```bash
cd server

# Install dependencies
poetry install

# Run dev server
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run all tests
poetry run pytest

# Run a single test file
poetry run pytest tests/test_api/test_system.py

# Run a single test by name
poetry run pytest -k "test_health"

# Lint + format
poetry run ruff check .
poetry run ruff format .

# Type check
poetry run mypy app/
```

### Frontend (web/)

```bash
cd web

# Install dependencies
npm install

# Dev server (proxies /api to localhost:8000)
npm run dev

# Build (runs type-check + vite build in parallel)
npm run build

# Lint (oxlint then eslint, both with --fix)
npm run lint

# Format
npm run format

# Type check only
npm run type-check
```

## Architecture

Monorepo with two workspaces: `server/` (Python 3.11+ / FastAPI / Poetry) and `web/` (Vue 3 / TypeScript / Vite / Tailwind v4).

### Backend Layering (strict one-way dependency)

```
API (app/api/) → Service (app/services/) → Repository (app/repositories/) → database
                                          → Core (app/core/)
```

- **API layer** — route handlers, request validation, response serialization. Never calls Core or Repository directly.
- **Service layer** — business orchestration, cross-module coordination.
- **Repository layer** — SQLite data access via aiosqlite.
- **Core layer** (`app/core/`) — pure domain logic, framework-independent:
  - `engine/` — `GameEngine` ABC + `GameEngineRegistry`. Engines are stateless; state flows through `GameState` dataclasses. New games register via the registry, no if-else chains.
  - `ai/` — `LLMClient` ABC + `LLMClientFactory`. Provider implementations: `OpenAICompatibleClient` (covers OpenAI, DashScope, DeepSeek, Kimi, ZhipuAI, Yi, Baichuan, MiniMax), `OllamaClient`. All configured via `dependencies.py`. Streaming supports `stream_options: {"include_usage": true}` for token usage tracking. `StreamChunk` carries optional `usage` field on the final chunk.
  - `collector/` — JSONL writer for game data.
  - `training/` — SFT dataset exporter (JSONL → ChatML format) + mock trainer (simulates progress). State machine: pending → exporting → training → completed/failed.
- **WebSocket** (`app/websocket/`) — `ConnectionManager` broadcasts per-game events; `handlers.py` contains WS endpoint logic.
- **Schemas** (`app/schemas/`) — Pydantic models for request/response. Shared `ApiResponse` envelope.
- **Config** — `app/config.py` uses `pydantic-settings`, reads from env vars / `.env` file at project root.

### Frontend Structure

- Vue 3 Composition API (`<script setup lang="ts">`) + Pinia stores + Vue Router
- `src/api/` — typed Axios client with interceptors; `src/stores/` — one store per domain
- `src/composables/` — `useWebSocket`, `usePagination`
- `src/components/` organized by domain: `game/`, `data/`, `trace/`, `common/`
- `src/views/` — `PipelineView`, `GameView`, `GameObserverView`, `AIPlayerView`, `DataView`, `TrainingView`, `PromptView`, `TraceView`, `DecisionView`, `SettingsView`
- Dual shells: `layouts/WorkbenchLayout.vue` (grouped nav) + `layouts/ObserverLayout.vue` (fullscreen)
- Headless UI kit: `components/ui/*` (Reka UI + Ink Lab tokens); charts via ECharts
- Runtime config: AI players + prompt templates in SQLite; secrets/paths via `.env`; `config/ai_players.yaml` is seed-only
- Vite dev server proxies `/api` → `localhost:8000` and WebSocket at `/api/v1/games/ws`

### Game Observer Features

- Real-time WebSocket observation with player cards, card display, action history
- Tabbed right panel: "出牌记录" (action history) | "AI 思考" (thinking panel)
- ThinkingPanel shows full AI reasoning per round with response time, token usage, collapsible entries
- PlayerCard displays response time badge, round/total token counts, and truncated thinking with expand link
- Replay mode for finished games: step-by-step playback with play/pause, prev/next, speed control
- Batch game creation: run 1-50 games at once for data collection

### Database Tables

`games`, `rounds`, `datasets`, `training_tasks`, `prompt_templates`, `traces`, `spans`, `decision_points` — all in SQLite via aiosqlite. Schema defined in `app/database.py`.

### Decision Points for SFT Training

Key decision points are recorded for supervised fine-tuning:

- **State-Action Pairs** — Every AI decision records: hand cards, opponent hand counts, last action, game phase, legal actions, chosen action, AI thinking
- **Quality Scoring** — After game ends, decisions are tagged with outcome (win/lose) and quality score (0.3-0.8)
- **ChatML Export** — Export decision points to ChatML format for SFT training

API endpoints:
- `GET /api/v1/decision-points` — List decision points (filter by game_id, player_id, quality)
- `GET /api/v1/decision-points/{id}` — Get decision point detail
- `GET /api/v1/decision-points/stats` — Aggregate statistics
- `POST /api/v1/decision-points/export` — Export to ChatML format

Frontend: `DecisionView.vue` with decision list and detail panels.

### AI Decision Observability

Lightweight observability platform for AI decision tracing:

- **Trace Recording** — Every AI decision records: game state snapshot, prompt version, LLM response, parsed action, metrics (response time, parser type)
- **Span Tracking** — Sub-operations (tool calls) tracked as independent spans
- **Performance Metrics** — Aggregated stats: avg/min/max response time, parser success rate
- **Prompt Version Comparison** — A/B testing support for prompt effectiveness
- **Real-time WebSocket** — Trace events broadcast to connected clients

API endpoints:
- `GET /api/v1/traces` — List traces (filter by game_id, player_id)
- `GET /api/v1/traces/{trace_id}` — Get trace detail with spans
- `GET /api/v1/traces/metrics` — Aggregated performance metrics
- `GET /api/v1/traces/compare` — Compare prompt versions

Frontend: `TraceView.vue` with `TraceDetail.vue` and `TraceMetrics.vue` components.

### Data Dashboard Features

The data overview page (`DataView.vue` → `OverviewTab` → `StatCards`) provides 5 statistical sections:

1. **Basic Stats** — Total games, total rounds, avg response time, game type count
2. **Token Usage** — Total/prompt/completion tokens, per-round average, per-model token bar chart
3. **Game Quality** — Avg game rounds, games with winner, decision rate, wins-by-role pie chart
4. **AI Performance** — Per-model win rate comparison bar chart (computed from games + rounds)
5. **Response Time** — P50/P95 percentile, per-model avg response time bar chart

Plus a model usage distribution pie chart (legacy).

Backend: `DataService.get_stats()` runs ~12 SQL queries aggregating from `games` and `rounds` tables.
Frontend: `StatCards.vue` renders stat cards and ECharts charts (Pie + Bar).

### Adding a New Card Game

1. Create `server/app/core/engine/<game_name>/` with engine implementation inheriting `GameEngine`
2. Register in `server/app/core/engine/__init__.py`
3. Implement `get_public_info(..., is_observer=True)` to emit the universal **ObserverSnapshot**
   (`game_type`, `phase`, `round`, `current_player_id`, `players[]`, `table.slots`, `extras`)
4. Optional: Prompt / Parser for the new game

**Do not** add `web/src/components/game/boards/<GameName>Board.vue` or branch `GameObserverView`
by `game_type`. Observation uses a single `GenericBoard` list board.

No API/Service/Repository changes needed — routing is automatic via `game_type`.

## Key Conventions

- 规范文档默认对新增代码和本次修改范围内的代码强制生效；存量代码按“发现即修、逐步收敛”推进。
- Python: all new or modified functions require full type annotations using 3.11+ syntax (`list[...]`, `X | Y`, `X | None`). Avoid `typing.List/Dict/Optional/Union`; when touching old code,补齐同范围内缺失的类型标注。
- Python: async for all I/O (LLM calls, DB, file). CPU-bound work goes to `asyncio.to_thread()`.
- Python: structlog for logging with key-value pairs, never f-strings in log calls.
- Python: custom exception hierarchy rooted at `AppError` (in `app/utils/exceptions.py`), caught by global handler.
- Python: Ruff for lint+format (line-length 100), mypy strict mode is the target standard for new and modified code.
- Frontend: strict TypeScript is the target standard; new and modified code must avoid `any`, and touched legacy code should be narrowed where practical.
- Frontend: use shared API error normalization in `src/api/client.ts` and shared UI-facing helpers such as `src/utils/error.ts` instead of scattering ad-hoc error display logic.
- Frontend: `@` alias maps to `web/src/`.
- Tests: pytest with `asyncio_mode = "auto"`. Test client uses `httpx.AsyncClient` with `ASGITransport`.
- Git: conventional commits `<type>(<scope>): <subject>`. Branches: `master`, `dev`, `feat/<name>`, `fix/<name>`.
- No cross-layer calls (API must not skip Service to reach Core/Repository).
- No global mutable state. No `print()` for debugging.
