"""API-layer tests for training guards + cancel (Task 4).

Covers:
- POST /training/tasks returns 400 TRAINING_GUARD_FAILED when guards reject.
- POST /training/tasks/{id}/cancel cancels a running task and returns 200.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import aiosqlite

from app import dependencies
from app.repositories.dataset_repo import DatasetRepository

if TYPE_CHECKING:
    from httpx import AsyncClient


async def _seed_dataset(client: AsyncClient) -> str:
    # Clear the lru_cached singleton so it rebinds to this test's sqlite path,
    # then seed a dataset row into the same DB the service will use.
    dependencies.get_training_service.cache_clear()
    service = dependencies.get_training_service()
    dataset_id = "dataset_api_smoke"
    async with aiosqlite.connect(service._sqlite_path) as db:
        db.row_factory = aiosqlite.Row
        repo = DatasetRepository(db)
        await repo.create(
            {
                "id": dataset_id,
                "name": "api-smoke",
                "game_type": "doudizhu",
                "filters": {},
                "sample_count": 2,
                "file_path": "datasets/api_smoke.jsonl",
                "created_at": datetime.now(tz=UTC).isoformat(),
            }
        )
    return dataset_id


async def test_create_training_task_guard_returns_400(client: AsyncClient, monkeypatch) -> None:
    import app.core.training.sft as sft_mod

    monkeypatch.setattr(sft_mod, "training_deps_available", lambda: False)

    res = await client.post(
        "/api/v1/training/tasks",
        json={
            "name": "guarded",
            "dataset_id": "any",
            "training_type": "sft",
            "base_model": "Qwen/Qwen2.5-1.5B",
            "config": {"use_mock": False},
        },
    )
    assert res.status_code == 400
    body = res.json()
    assert body["code"] == "TRAINING_GUARD_FAILED"
    assert "Training deps missing" in body["message"]


async def test_cancel_training_task(client: AsyncClient) -> None:
    dataset_id = await _seed_dataset(client)

    # Force the singleton service to non-mock-default-agnostic: use mock=True
    # so guards do not fire, and replace the pipeline with a long sleep.
    dependencies.get_training_service.cache_clear()
    service = dependencies.get_training_service()
    original_pipeline = service._run_pipeline

    async def slow_pipeline(
        task_id: str,
        _dataset: dict[str, Any],
        _cancel_flag: dict[str, bool] | None = None,
    ) -> None:
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            await service._update(task_id, "cancelled")
            raise

    service._run_pipeline = slow_pipeline  # type: ignore[method-assign]
    try:
        create_res = await client.post(
            "/api/v1/training/tasks",
            json={
                "name": "cancel-api",
                "dataset_id": dataset_id,
                "config": {"use_mock": True},
            },
        )
        assert create_res.status_code == 201
        task_id = create_res.json()["data"]["id"]

        # Let the bg task actually start sleeping.
        await asyncio.sleep(0)
        cancel_res = await client.post(f"/api/v1/training/tasks/{task_id}/cancel")
        assert cancel_res.status_code == 200
        assert cancel_res.json()["data"]["status"] == "cancelled"
    finally:
        service._run_pipeline = original_pipeline  # type: ignore[method-assign]
