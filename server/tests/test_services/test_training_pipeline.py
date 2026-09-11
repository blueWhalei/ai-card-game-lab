"""Training orchestration uses fake trainers and real isolated persistence."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.database import connect_sqlite, init_db
from app.repositories.dataset_repo import DatasetRepository
from app.schemas.training import CreateTrainingTaskRequest
from app.services.training_service import TrainingService


@pytest.fixture
async def pipeline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TrainingService:
    sqlite = str(tmp_path / "train.db")
    await init_db(sqlite)
    (tmp_path / "sample.jsonl").write_text('{"messages":[]}\n', encoding="utf-8")
    async with connect_sqlite(sqlite) as db:
        await DatasetRepository(db).create(
            {
                "id": "ds",
                "name": "fixture",
                "game_type": "doudizhu",
                "filters": {},
                "file_path": "sample.jsonl",
                "sample_count": 1,
                "created_at": datetime.now(UTC).isoformat(),
            }
        )
    service = TrainingService(sqlite, str(tmp_path), str(tmp_path / "models"))
    monkeypatch.setattr(
        service, "_apply_cpu_smoke_guards", AsyncMock(side_effect=lambda cfg, **kwargs: cfg)
    )
    return service


async def launch(service: TrainingService) -> tuple[str, asyncio.Task[None]]:
    record = await service.create_task(CreateTrainingTaskRequest(name="test", dataset_id="ds"))
    task_id = str(record["id"])
    return task_id, service._running_tasks[task_id]


async def test_success_persists_artifact_and_releases_runtime(
    pipeline: TrainingService, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def trainer(**kwargs: Any) -> dict[str, Any]:
        await kwargs["on_progress"](0.5)
        adapter = Path(kwargs["output_dir"]) / "adapter"
        adapter.mkdir()
        (adapter / "adapter_config.json").write_text("{}", encoding="utf-8")
        return {"adapter_path": str(adapter)}

    monkeypatch.setattr("app.services.training_service.run_sft_training", trainer)
    task_id, background = await launch(pipeline)
    await background
    result = await pipeline.get_task(task_id)
    assert result["status"] == "completed"
    assert result["progress"] == 1
    assert Path(result["model_path"]).is_dir()
    assert task_id not in pipeline._running_tasks
    assert task_id not in pipeline._cancel_flags


@pytest.mark.parametrize("outcome", ["missing", "exception"])
async def test_failed_training_does_not_register_a_model(
    pipeline: TrainingService, monkeypatch: pytest.MonkeyPatch, outcome: str
) -> None:
    trainer = AsyncMock(return_value={})
    if outcome == "exception":
        trainer.side_effect = OSError("cannot write adapter")
    monkeypatch.setattr("app.services.training_service.run_sft_training", trainer)
    task_id, background = await launch(pipeline)
    await background
    result = await pipeline.get_task(task_id)
    assert result["status"] == "failed"
    assert result["result"]["error"]
    assert not result["model_path"]
    assert await pipeline.list_models() == []
    assert task_id not in pipeline._running_tasks


async def test_cancellation_signals_trainer_and_keeps_terminal_status(
    pipeline: TrainingService, monkeypatch: pytest.MonkeyPatch
) -> None:
    entered = asyncio.Event()
    flags = []

    async def trainer(**kwargs: Any) -> dict[str, Any]:
        flags.append(kwargs["cancel_flag"])
        entered.set()
        await asyncio.Event().wait()
        return {}

    monkeypatch.setattr("app.services.training_service.run_sft_training", trainer)
    task_id, background = await launch(pipeline)
    await asyncio.wait_for(entered.wait(), 5)
    await pipeline.cancel_task(task_id)
    await background
    assert flags[0]["cancel"] is True
    assert (await pipeline.get_task(task_id))["status"] == "cancelled"
    assert task_id not in pipeline._cancel_flags
    with pytest.raises(ValueError, match="terminal"):
        await pipeline.cancel_task(task_id)


async def test_empty_dataset_never_calls_trainer(
    pipeline: TrainingService, monkeypatch: pytest.MonkeyPatch
) -> None:
    Path(pipeline._data_dir, "sample.jsonl").write_text("", encoding="utf-8")
    async with connect_sqlite(pipeline._sqlite_path) as db:
        await db.execute("UPDATE datasets SET sample_count=0")
        await db.commit()
    trainer = AsyncMock()
    monkeypatch.setattr("app.services.training_service.run_sft_training", trainer)
    task_id, background = await launch(pipeline)
    await background
    trainer.assert_not_awaited()
    assert (await pipeline.get_task(task_id))["status"] == "failed"
