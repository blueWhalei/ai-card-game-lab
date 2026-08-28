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


async def _noop_pipeline(
    _task_id: str,
    _dataset: dict[str, Any],
    _cancel_flag: dict[str, bool] | None = None,
) -> None:
    """Replace the background pipeline so tests never actually train."""
    return None


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


async def test_create_training_task_rejects_max_steps_zero(client: AsyncClient) -> None:
    """C1: max_steps has ge=1; sending 0 must 422 so the FE omits it on Mock."""
    dataset_id = await _seed_dataset(client)
    res = await client.post(
        "/api/v1/training/tasks",
        json={
            "name": "zero-steps",
            "dataset_id": dataset_id,
            "config": {"use_mock": True, "max_steps": 0},
        },
    )
    assert res.status_code == 422


async def test_create_training_task_mock_without_max_steps(client: AsyncClient) -> None:
    """C1: Mock create with max_steps omitted must succeed (FE contract)."""
    dataset_id = await _seed_dataset(client)
    dependencies.get_training_service.cache_clear()
    service = dependencies.get_training_service()
    original_pipeline = service._run_pipeline
    service._run_pipeline = _noop_pipeline  # type: ignore[method-assign]
    try:
        res = await client.post(
            "/api/v1/training/tasks",
            json={
                "name": "mock-no-steps",
                "dataset_id": dataset_id,
                "config": {"use_mock": True},
            },
        )
        assert res.status_code == 201
        cfg = res.json()["data"]["config"]
        assert cfg["use_mock"] is True
        assert "max_steps" not in cfg or cfg["max_steps"] is None
    finally:
        service._run_pipeline = original_pipeline  # type: ignore[method-assign]


async def test_cancel_terminal_task_returns_400(client: AsyncClient) -> None:
    """I4: cancelling a completed task must not overwrite its terminal status."""
    dataset_id = await _seed_dataset(client)
    dependencies.get_training_service.cache_clear()
    service = dependencies.get_training_service()
    original_pipeline = service._run_pipeline
    service._run_pipeline = _noop_pipeline  # type: ignore[method-assign]
    try:
        create_res = await client.post(
            "/api/v1/training/tasks",
            json={
                "name": "completed-task",
                "dataset_id": dataset_id,
                "config": {"use_mock": True},
            },
        )
        task_id = create_res.json()["data"]["id"]

        # Force the task into a terminal state.
        await service._update(
            task_id, "completed", progress=1.0, finished_at=datetime.now(tz=UTC).isoformat()
        )

        cancel_res = await client.post(f"/api/v1/training/tasks/{task_id}/cancel")
        assert cancel_res.status_code == 400
        body = cancel_res.json()
        assert body["code"] == "TRAINING_GUARD_FAILED"
        assert "already 'completed'" in body["message"]

        # The terminal status must be preserved.
        get_res = await client.get(f"/api/v1/training/tasks/{task_id}")
        assert get_res.json()["data"]["status"] == "completed"
    finally:
        service._run_pipeline = original_pipeline  # type: ignore[method-assign]
