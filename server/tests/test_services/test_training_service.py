from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import aiosqlite
import pytest

from app.core.training.exporter import export_sft_dataset
from app.database import init_db
from app.repositories.dataset_repo import DatasetRepository
from app.schemas.training import CreateTrainingTaskRequest, TrainingConfig
from app.services.training_service import TrainingService
from app.utils.exceptions import DatasetNotFoundError, TrainingTaskNotFoundError


@pytest.mark.asyncio
async def test_create_task_raises_dataset_not_found(tmp_path: Path) -> None:
    service = TrainingService(
        sqlite_path=str(tmp_path / "missing.db"),
        data_dir=str(tmp_path / "data"),
        models_dir=str(tmp_path / "models"),
    )
    await init_db(str(tmp_path / "missing.db"))

    request = CreateTrainingTaskRequest(
        name="missing-dataset",
        dataset_id="dataset_missing",
        base_model="Qwen/Qwen2.5-1.5B",
        training_type="sft",
        config=TrainingConfig(
            learning_rate=2e-5,
            batch_size=8,
            num_epochs=3,
            output_format="pytorch",
        ),
    )

    with pytest.raises(DatasetNotFoundError):
        await service.create_task(request)


@pytest.mark.asyncio
async def test_get_bg_db_sets_row_factory(tmp_path: Path) -> None:
    service = TrainingService(
        sqlite_path=str(tmp_path / "training.db"),
        data_dir=str(tmp_path / "data"),
        models_dir=str(tmp_path / "models"),
    )

    async with service._get_bg_db() as db:
        assert db.row_factory is not None


async def _seed_completed_task_with_files(
    tmp_path: Path,
    *,
    task_id: str = "task_del_1",
) -> TrainingService:
    sqlite_path = str(tmp_path / "del.db")
    data_dir = tmp_path / "data"
    models_dir = tmp_path / "models"
    await init_db(sqlite_path)
    data_dir.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(sqlite_path) as db:
        db.row_factory = aiosqlite.Row
        repo = DatasetRepository(db)
        await repo.create(
            {
                "id": "ds_del",
                "name": "del-ds",
                "game_type": "doudizhu",
                "filters": {},
                "sample_count": 1,
                "file_path": "datasets/x.jsonl",
                "created_at": datetime.now(tz=UTC).isoformat(),
            }
        )

    adapter = models_dir / task_id / "adapter"
    adapter.mkdir(parents=True)
    (adapter / "adapter_config.json").write_text("{}", encoding="utf-8")
    (models_dir / task_id / "deploy").mkdir(parents=True)
    (models_dir / task_id / "deploy" / "model.gguf").write_bytes(b"gguf")

    service = TrainingService(
        sqlite_path=sqlite_path,
        data_dir=str(data_dir),
        models_dir=str(models_dir),
    )
    async with service._get_bg_db() as db:
        from app.repositories.training_repo import TrainingTaskRepository

        repo = TrainingTaskRepository(db)
        await repo.create(
            {
                "id": task_id,
                "name": "to-delete",
                "dataset_id": "ds_del",
                "base_model": "Qwen/Qwen2.5-0.5B",
                "training_type": "sft",
                "config": {},
                "status": "pending",
                "progress": 0,
                "created_at": datetime.now(tz=UTC).isoformat(),
            }
        )
        await repo.update_status(
            task_id,
            "completed",
            progress=1.0,
            model_path=str(adapter),
            finished_at=datetime.now(tz=UTC).isoformat(),
        )
    return service


@pytest.mark.asyncio
async def test_delete_model_clears_db_and_removes_files(tmp_path: Path) -> None:
    task_id = "task_del_model"
    service = await _seed_completed_task_with_files(tmp_path, task_id=task_id)
    model_root = Path(service._models_dir) / task_id
    assert model_root.is_dir()

    await service.delete_model(task_id)

    assert not model_root.exists()
    task = await service.get_task(task_id)
    assert task["model_path"] is None
    models = await service.list_models()
    assert all(m["id"] != task_id for m in models)


@pytest.mark.asyncio
async def test_delete_task_removes_row_and_files(tmp_path: Path) -> None:
    task_id = "task_del_task"
    service = await _seed_completed_task_with_files(tmp_path, task_id=task_id)
    model_root = Path(service._models_dir) / task_id
    assert model_root.is_dir()

    await service.delete_task(task_id)

    assert not model_root.exists()
    with pytest.raises(TrainingTaskNotFoundError):
        await service.get_task(task_id)
