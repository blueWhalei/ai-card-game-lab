"""API smoke for distill preference export."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from httpx import AsyncClient

from app.config import Settings
from app.database import connect_sqlite
from app.repositories.experiment_repo import ExperimentRepository
from app.repositories.game_repo import GameRepository
from app.services.decision_service import DecisionService
from tests.test_core.test_training.test_distill import sample


async def test_export_distill_preferences_empty(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/decision-points/export-distill-preferences",
        json={
            "teacher_experiment_id": "exp_teacher_missing",
            "student_experiment_id": "exp_student_missing",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["count"] == 0
    assert body["data"]["filepath"] == ""
    assert "No distill" in body["message"]


async def test_export_uses_verified_history_and_reports_exclusions(
    client: AsyncClient, test_settings: Settings
) -> None:
    now = datetime.now(tz=UTC).isoformat()
    engine = {
        "game_type": "doudizhu",
        "engine_version": "1",
        "decision_schema_version": 3,
        "rules_ref": "rules",
    }
    async with connect_sqlite(test_settings.sqlite_path) as db:
        for side in ("a", "b"):
            await ExperimentRepository(db).create(
                experiment_id=side,
                name=side,
                notes="",
                game_type="doudizhu",
                player_ids=[f"{side}{i}" for i in range(3)],
                target_games=1,
                created_at=now,
                updated_at=now,
                protocol={"schema_version": 2, "engine": engine},
            )
            await GameRepository(db).create(
                game_id=side,
                game_type="doudizhu",
                player_ids=[f"{side}{i}" for i in range(3)],
                data_file="unused.jsonl",
                created_at=now,
                status="finished",
                metadata={"deal_seed": 7},
                experiment_id=side,
            )
            await GameRepository(db).update_result(
                side,
                winner_id=f"{side}0",
                winner_role="landlord",
                total_rounds=3,
                finished_at=now,
                metadata_patch={"landlord_id": f"{side}0"},
            )
    service = DecisionService(test_settings.sqlite_path, test_settings.data_dir)
    for side in ("a", "b"):
        for turn in range(3):
            point = sample(side, turn, 3 if side == "b" and turn > 0 else 1)
            point.pop("id")
            await service.create_decision_point(**point)
    response = await client.post(
        "/api/v1/decision-points/export-distill-preferences",
        json={
            "teacher_experiment_id": "a",
            "student_experiment_id": "b",
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()["data"]
    assert result["count"] == 1 and result["skipped_different_path"] == 1
    record = json.loads(Path(result["filepath"]).read_text(encoding="utf-8"))
    assert record["metadata"]["round_number"] == 1
    assert record["metadata"]["preference_source"] == "teacher_choice"
    async with connect_sqlite(test_settings.sqlite_path) as db:
        await ExperimentRepository(db).update_protocol(
            "b", {"schema_version": 2, "engine": {**engine, "engine_version": "2"}}
        )
    mismatch = await client.post(
        "/api/v1/decision-points/export-distill-preferences",
        json={
            "teacher_experiment_id": "a",
            "student_experiment_id": "b",
        },
    )
    assert mismatch.status_code == 400
    assert mismatch.json()["code"] == "DISTILL_PROTOCOL_MISMATCH"
