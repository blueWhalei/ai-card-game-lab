"""Descriptive navigation through current records; no new evaluation or inference."""

from datetime import UTC, datetime
from typing import Any

import aiosqlite

from app.core.stats.scenarios import ENDGAME_MAX_HAND, SCENARIO_IDS
from app.repositories.decision_repo import DecisionRepository
from app.repositories.experiment_repo import ExperimentRepository
from app.services.experiment_errors import ExperimentNotFoundError
from app.utils.exceptions import AppError


async def scenario_records(
    db: aiosqlite.Connection,
    experiment_id: str,
    scenario: str | None,
    game_id: str | None,
    decision_id: str | None,
    game_page: int,
    page: int,
) -> dict[str, Any]:
    try:
        run = await ExperimentRepository(db).get_by_id(experiment_id)
    except KeyError as exc:
        raise ExperimentNotFoundError(experiment_id) from exc
    if run["game_type"] != "doudizhu":
        raise AppError(
            "Scenario classification is defined only for Dou Dizhu", "SCENARIO_UNSUPPORTED", 422
        )
    if scenario is not None and scenario not in SCENARIO_IDS:
        raise AppError("Unknown scenario", "SCENARIO_INVALID", 422)
    result = await DecisionRepository(db).scenario_records(
        experiment_id, scenario, game_id, game_page, page
    )
    if game_id is not None and result["selected_game"] is None:
        raise AppError(
            "Game has no records in this run and scenario", "SCENARIO_SELECTION_MISSING", 422
        )
    if decision_id is not None and not any(
        point["id"] == decision_id for point in result["decisions"]["items"]
    ):
        raise AppError("Decision is not on the selected page", "SCENARIO_SELECTION_MISSING", 422)
    by_id = {group["scenario"]: group for group in result["groups"]}
    result["groups"] = [
        by_id.get(sid, {"scenario": sid, "decision_n": 0, "game_n": 0, "evaluated_n": 0})
        for sid in SCENARIO_IDS
    ]
    return {
        "experiment_id": experiment_id,
        "scope": "current_records",
        "read_at": datetime.now(UTC).isoformat(),
        "endgame_max_hand": ENDGAME_MAX_HAND,
        "scenario": scenario,
        **result,
    }
