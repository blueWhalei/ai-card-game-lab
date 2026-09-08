"""CardLab MCP tools (read + collect write; used by the server and unit tests)."""

from __future__ import annotations

from typing import Any

from app.database import open_db_connection
from app.mcp.serialize import truncate_decision_item
from app.services.decision_service import DecisionService
from app.services.experiment_service import ExperimentService

_LIST_DECISIONS_HARD_CAP = 100
_LIST_DECISIONS_DEFAULT = 20
_COLLECT_COUNT_MIN = 1
_COLLECT_COUNT_MAX = 50


async def list_experiments(experiment_service: ExperimentService) -> dict[str, Any]:
    """Return experiment list rows (same shape as the home list API)."""
    items = await experiment_service.list_experiments()
    return {"count": len(items), "items": items}


async def get_experiment(
    experiment_service: ExperimentService,
    experiment_id: str,
    *,
    include_games: bool = False,
) -> dict[str, Any]:
    """Return one experiment detail; games omitted by default."""
    return await experiment_service.get_experiment(
        experiment_id,
        include_games=include_games,
    )


async def list_decision_points(
    decision_service: DecisionService,
    *,
    experiment_id: str | None = None,
    game_id: str | None = None,
    train_usable: bool | None = None,
    max_ev_loss: float | None = None,
    limit: int = _LIST_DECISIONS_DEFAULT,
) -> dict[str, Any]:
    """Page decision points with light field truncation."""
    capped = max(1, min(int(limit), _LIST_DECISIONS_HARD_CAP))
    items, total = await decision_service.list_decision_points(
        experiment_id=experiment_id,
        game_id=game_id,
        train_usable=train_usable,
        max_ev_loss=max_ev_loss,
        limit=capped,
        offset=0,
    )
    return {
        "total": total,
        "count": len(items),
        "limit": capped,
        "items": [truncate_decision_item(item) for item in items],
    }


async def get_decision_stats(
    decision_service: DecisionService,
    *,
    experiment_id: str | None = None,
) -> dict[str, Any]:
    """Aggregate decision-point statistics."""
    return await decision_service.get_stats(experiment_id=experiment_id)


async def start_collect(
    experiment_service: ExperimentService,
    experiment_id: str,
    *,
    count: int = 1,
) -> dict[str, Any]:
    """Start collecting games for an experiment (may spend API budget)."""
    capped = max(_COLLECT_COUNT_MIN, min(int(count), _COLLECT_COUNT_MAX))
    db = await open_db_connection(experiment_service._sqlite_path)
    try:
        result = await experiment_service.collect(experiment_id, count=capped, db=db)
    finally:
        await db.close()
    return {"ok": True, **result}


async def cancel_collect(
    experiment_service: ExperimentService,
    experiment_id: str,
) -> dict[str, Any]:
    """Cancel in-flight collect games for an experiment."""
    result = await experiment_service.cancel_collect(experiment_id)
    return {"ok": True, **result}
