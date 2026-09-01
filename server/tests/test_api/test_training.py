"""API-layer tests for training guards + cancel (Task 4).

Covers:
- POST /training/tasks returns 400 TRAINING_GUARD_FAILED when guards reject.
- POST /training/tasks/{id}/cancel cancels a running task and returns 200.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
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
            "config": {},
        },
    )
    assert res.status_code == 400
    body = res.json()
    assert body["code"] == "TRAINING_GUARD_FAILED"
    assert "Training deps missing" in body["message"]


async def test_cancel_training_task(client: AsyncClient, monkeypatch) -> None:
    dataset_id = await _seed_dataset(client)

    import app.core.training.sft as sft_mod
    import app.services.training_service as svc_mod

    monkeypatch.setattr(sft_mod, "training_deps_available", lambda: True)
    monkeypatch.setattr(svc_mod, "_probe_cuda_available", lambda: True)

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
                "config": {},
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
    """C1: max_steps has ge=1; sending 0 must 422."""
    dataset_id = await _seed_dataset(client)
    res = await client.post(
        "/api/v1/training/tasks",
        json={
            "name": "zero-steps",
            "dataset_id": dataset_id,
            "config": {"max_steps": 0},
        },
    )
    assert res.status_code == 422


async def test_create_training_task_without_max_steps(
    client: AsyncClient, monkeypatch
) -> None:
    """Create with max_steps omitted must succeed (FE contract)."""
    import app.core.training.sft as sft_mod
    import app.services.training_service as svc_mod

    monkeypatch.setattr(sft_mod, "training_deps_available", lambda: True)
    monkeypatch.setattr(svc_mod, "_probe_cuda_available", lambda: True)

    dataset_id = await _seed_dataset(client)
    dependencies.get_training_service.cache_clear()
    service = dependencies.get_training_service()
    original_pipeline = service._run_pipeline
    service._run_pipeline = _noop_pipeline  # type: ignore[method-assign]
    try:
        res = await client.post(
            "/api/v1/training/tasks",
            json={
                "name": "no-steps",
                "dataset_id": dataset_id,
                "config": {},
            },
        )
        assert res.status_code == 201
        cfg = res.json()["data"]["config"]
        assert "use_mock" not in cfg
        assert "max_steps" not in cfg or cfg["max_steps"] is None
    finally:
        service._run_pipeline = original_pipeline  # type: ignore[method-assign]


async def test_cancel_terminal_task_returns_400(client: AsyncClient, monkeypatch) -> None:
    """I4: cancelling a completed task must not overwrite its terminal status."""
    import app.core.training.sft as sft_mod
    import app.services.training_service as svc_mod

    monkeypatch.setattr(sft_mod, "training_deps_available", lambda: True)
    monkeypatch.setattr(svc_mod, "_probe_cuda_available", lambda: True)

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
                "config": {},
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


async def test_create_and_list_task_by_experiment(client: AsyncClient, monkeypatch) -> None:
    dataset_id = await _seed_dataset(client)
    exp_res = await client.post(
        "/api/v1/experiments",
        json={
            "name": "link-train",
            "player_ids": ["cfg_temp_09", "cfg_temp_06", "cfg_temp_12"],
            "target_games": 1,
        },
    )
    assert exp_res.status_code == 201, exp_res.text
    exp_id = exp_res.json()["data"]["id"]

    import app.core.training.sft as sft_mod
    import app.services.training_service as svc_mod

    monkeypatch.setattr(sft_mod, "training_deps_available", lambda: True)
    monkeypatch.setattr(svc_mod, "_probe_cuda_available", lambda: True)

    dependencies.get_training_service.cache_clear()
    service = dependencies.get_training_service()
    original_pipeline = service._run_pipeline
    service._run_pipeline = _noop_pipeline  # type: ignore[method-assign]
    try:
        create_res = await client.post(
            "/api/v1/training/tasks",
            json={
                "name": "exp-linked",
                "dataset_id": dataset_id,
                    "experiment_id": exp_id,
                "config": {},
            },
        )
        assert create_res.status_code == 201, create_res.text
        assert create_res.json()["data"]["experiment_id"] == exp_id

        listed = await client.get(
            "/api/v1/training/tasks",
            params={"experiment_id": exp_id},
        )
        assert listed.status_code == 200
        items = listed.json()["data"]["items"]
        assert len(items) == 1
        assert items[0]["name"] == "exp-linked"

        other = await client.get(
            "/api/v1/training/tasks",
            params={"experiment_id": "exp_missing"},
        )
        assert other.json()["data"]["total"] == 0
    finally:
        service._run_pipeline = original_pipeline  # type: ignore[method-assign]


async def test_push_ollama_rejects_non_lora(client: AsyncClient, monkeypatch) -> None:
    dataset_id = await _seed_dataset(client)

    import app.core.training.sft as sft_mod
    import app.services.training_service as svc_mod

    monkeypatch.setattr(sft_mod, "training_deps_available", lambda: True)
    monkeypatch.setattr(svc_mod, "_probe_cuda_available", lambda: True)

    dependencies.get_training_service.cache_clear()
    service = dependencies.get_training_service()
    models_root = Path(service._data_dir) / "models"
    models_root.mkdir(parents=True, exist_ok=True)
    service._models_dir = str(models_root)
    original_pipeline = service._run_pipeline
    service._run_pipeline = _noop_pipeline  # type: ignore[method-assign]
    try:
        create_res = await client.post(
            "/api/v1/training/tasks",
            json={"name": "bin-model", "dataset_id": dataset_id, "config": {}},
        )
        task_id = create_res.json()["data"]["id"]
        blob = models_root / task_id / "model.bin"
        blob.parent.mkdir(parents=True, exist_ok=True)
        blob.write_text("placeholder", encoding="utf-8")
        await service._update(
            task_id,
            "completed",
            progress=1.0,
            model_path=str(blob),
            finished_at=datetime.now(tz=UTC).isoformat(),
        )

        res = await client.post(f"/api/v1/models/{task_id}/push-ollama", json={})
        assert res.status_code == 400
        assert res.json()["code"] == "DEPLOY_NOT_LORA"
    finally:
        service._run_pipeline = original_pipeline  # type: ignore[method-assign]


async def test_push_ollama_missing_llama_cpp(client: AsyncClient, monkeypatch) -> None:
    dataset_id = await _seed_dataset(client)

    import app.core.training.deploy as deploy_mod
    import app.core.training.sft as sft_mod
    import app.services.training_service as svc_mod

    monkeypatch.setattr(sft_mod, "training_deps_available", lambda: True)
    monkeypatch.setattr(svc_mod, "_probe_cuda_available", lambda: True)

    dependencies.get_training_service.cache_clear()
    service = dependencies.get_training_service()
    models_root = Path(service._data_dir) / "models"
    models_root.mkdir(parents=True, exist_ok=True)
    service._models_dir = str(models_root)
    service._llama_cpp_dir = ""
    original_pipeline = service._run_pipeline
    service._run_pipeline = _noop_pipeline  # type: ignore[method-assign]

    def _fake_merge(*, base_model: str, adapter_path: str | Path, output_dir: str | Path) -> str:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "config.json").write_text("{}", encoding="utf-8")
        return str(out)

    monkeypatch.setattr(deploy_mod, "merge_lora_to_hf", _fake_merge)

    try:
        create_res = await client.post(
            "/api/v1/training/tasks",
            json={"name": "lora-push", "dataset_id": dataset_id, "config": {}},
        )
        task_id = create_res.json()["data"]["id"]
        adapter = models_root / task_id / "adapter"
        adapter.mkdir(parents=True, exist_ok=True)
        (adapter / "adapter_config.json").write_text("{}", encoding="utf-8")
        await service._update(
            task_id,
            "completed",
            progress=1.0,
            model_path=str(adapter),
            finished_at=datetime.now(tz=UTC).isoformat(),
        )

        res = await client.post(f"/api/v1/models/{task_id}/push-ollama", json={})
        assert res.status_code == 400
        assert res.json()["code"] == "DEPLOY_LLAMA_CPP_MISSING"
    finally:
        service._run_pipeline = original_pipeline  # type: ignore[method-assign]
