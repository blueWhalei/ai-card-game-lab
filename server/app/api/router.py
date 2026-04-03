"""Top-level API router that aggregates all versioned sub-routers."""

from fastapi import APIRouter

from app.api.v1 import (
    ai_player,
    data,
    decision,
    game,
    migration,
    player_stats,
    prompt,
    system,
    trace,
    training,
)

api_router = APIRouter()

api_router.include_router(system.router, prefix="/api/v1/system", tags=["system"])
api_router.include_router(game.router, prefix="/api/v1/games", tags=["games"])
api_router.include_router(player_stats.router, prefix="/api/v1/ai-players", tags=["ai-players"])
api_router.include_router(ai_player.router, prefix="/api/v1/ai-players", tags=["ai-players"])
api_router.include_router(data.router, prefix="/api/v1", tags=["data"])
api_router.include_router(training.router, prefix="/api/v1", tags=["training"])
api_router.include_router(prompt.router, prefix="/api/v1/prompts", tags=["prompts"])
api_router.include_router(trace.router, prefix="/api/v1/traces", tags=["traces"])
api_router.include_router(
    decision.router, prefix="/api/v1/decision-points", tags=["decision-points"]
)
api_router.include_router(migration.router, prefix="/api/v1/migration", tags=["migration"])
