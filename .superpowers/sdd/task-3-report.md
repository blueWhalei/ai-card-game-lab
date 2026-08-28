# Task 3 Report: API + dependencies + callers

## Status

**Complete.** App imports cleanly; `/api/v1/experiment-configs` CRUD + stats exposed; all callers rewired to `ExperimentConfigService`.

## TDD workflow

1. **Red** — Wrote `tests/test_api/test_experiment_configs.py` first (`test_list_and_stats`, CRUD, conflict). Initial run blocked by `ModuleNotFoundError: ai_player_service` (Task 2 deletion).
2. **Green** — Implemented routers, dependencies, caller updates, deleted legacy modules. Fixed conftest to `await get_experiment_config_service().initialize()` (ASGITransport does not run lifespan).
3. **Verify** — Targeted pytest + full collection.

## Changes

### Created
- `server/app/api/v1/experiment_config.py` — CRUD at `/api/v1/experiment-configs`; errors `EXPERIMENT_CONFIG_NOT_FOUND` / `EXPERIMENT_CONFIG_CONFLICT`
- `server/app/api/v1/experiment_config_stats.py` — `GET /stats` and `GET /{id}/stats`; stats list uses `ExperimentConfigService.list_configs()` ids
- `server/tests/test_api/test_experiment_configs.py` — list/stats, CRUD, conflict

### Modified
- `server/app/api/router.py` — mount stats router **before** config router; remove ai-players routes
- `server/app/dependencies.py` — `get_experiment_config_service`, `get_experiment_config_stats_service`; yaml `experiment_configs.yaml`; rewire orchestration/AI deps
- `server/app/main.py` — lifespan calls `get_experiment_config_service().initialize()`
- `server/app/services/ai_service.py` — removed unused `AIPlayerService` injection
- `server/app/services/game_orchestration_service.py` — `get_config` instead of `get_player`
- `server/app/services/training_service.py` — verify helpers use `create_config` / `update_config` with `notes=""`
- `server/app/services/experiment_config_stats_service.py` — added `get_config_stats` + `last_game_id`
- `server/tests/conftest.py` — cache clears + explicit experiment config initialize

### Deleted
- `server/app/api/v1/ai_player.py`
- `server/app/api/v1/player_stats.py`
- `server/app/services/player_stats_service.py`
- `server/app/repositories/player_stats_repo.py`

## Test results

```bash
cd server
poetry run pytest --collect-only -q
# 197 tests collected in 0.43s

poetry run pytest tests/test_api/test_experiment_configs.py tests/test_services/ -k experiment_config -v
# 7 passed
```

| Test | Result |
|------|--------|
| `test_list_and_stats` | PASS |
| `test_create_get_update_delete` | PASS |
| `test_create_conflict` | PASS |
| `test_experiment_configs_seed_and_crud` | PASS |
| `test_migrate_retired_deepseek_models` | PASS |
| `test_migrate_ai_players_to_experiment_configs` | PASS |
| `test_count_games_played_with_underscore_id` | PASS |

Full suite: 169 passed; 20 failed + 8 errors are pre-existing (websocket mocks, outdated `test_game_service` fixture) — unrelated to this task.

## Concerns / follow-ups

- **Task 4 (frontend)** still references `/api/v1/ai-players` — must switch to `/api/v1/experiment-configs`.
- **`schemas/ai_player.py`** orphaned; safe to delete in cleanup.
- **`scripts/e2e_pipeline.py`** still mentions `ai_players.yaml`.
- **conftest** manually initializes experiment configs because httpx `ASGITransport` has no lifespan hook; production lifespan handles this correctly.

## Commit

```
feat(experiment-config): expose /api/v1/experiment-configs and rewire callers
```
