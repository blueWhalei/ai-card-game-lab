"""Guards + cancel for TrainingService (Task 4).

Covers:
- create_task refuses non-mock CPU path when deps missing or RAM < 8GB.
- create_task applies CPU smoke clamps and persists clamped config.
- mock path remains unchanged (no guards fired).
- cancel_task sets the per-task cancel flag and cancels the bg asyncio task.
- export_model refuses a mock ``model.bin`` placeholder.
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiosqlite
import pytest

from app.database import init_db
from app.repositories.dataset_repo import DatasetRepository
from app.schemas.training import CreateTrainingTaskRequest, TrainingConfig
from app.services.training_service import TrainingService


async def _seed_dataset(sqlite_path: str, tmp_path: Path) -> str:
    """Insert a minimal dataset row and return its id."""
    dataset_id = "dataset_smoke"
    async with aiosqlite.connect(sqlite_path) as db:
        db.row_factory = aiosqlite.Row
        repo = DatasetRepository(db)
        await repo.create(
            {
                "id": dataset_id,
                "name": "smoke-dataset",
                "game_type": "doudizhu",
                "filters": {},
                "sample_count": 4,
                "file_path": "datasets/smoke.jsonl",
                "created_at": datetime.now(tz=UTC).isoformat(),
            }
        )
    # Also create the underlying file so a real pipeline would not crash early.
    data_dir = Path(sqlite_path).parent
    ds_file = data_dir / "datasets" / "smoke.jsonl"
    ds_file.parent.mkdir(parents=True, exist_ok=True)
    ds_file.write_text(
        '{"messages":[{"role":"user","content":"hi"},{"role":"assistant","content":"yo"}]}\n',
        encoding="utf-8",
    )
    return dataset_id


def _no_pipeline(service: TrainingService) -> None:
    """Replace the background pipeline with a noop so tests never train."""

    async def noop(
        _task_id: str,
        _dataset: dict[str, Any],
        _cancel_flag: dict[str, bool] | None = None,
    ) -> None:
        return None

    service._run_pipeline = noop  # type: ignore[method-assign]


@pytest.mark.asyncio
async def test_create_task_rejects_when_deps_missing(tmp_path: Path, monkeypatch) -> None:
    sqlite_path = str(tmp_path / "guards.db")
    await init_db(sqlite_path)
    service = TrainingService(
        sqlite_path=sqlite_path,
        data_dir=str(tmp_path / "data"),
        models_dir=str(tmp_path / "models"),
        training_use_mock=False,
    )
    _no_pipeline(service)

    import app.core.training.sft as sft_mod

    monkeypatch.setattr(sft_mod, "training_deps_available", lambda: False)

    request = CreateTrainingTaskRequest(
        name="no-deps",
        dataset_id="dataset_any",
        config=TrainingConfig(use_mock=False),
    )
    with pytest.raises(ValueError, match="Training deps missing"):
        await service.create_task(request)


@pytest.mark.asyncio
async def test_create_task_rejects_low_memory(tmp_path: Path, monkeypatch) -> None:
    sqlite_path = str(tmp_path / "guards.db")
    await init_db(sqlite_path)
    service = TrainingService(
        sqlite_path=sqlite_path,
        data_dir=str(tmp_path / "data"),
        models_dir=str(tmp_path / "models"),
        training_use_mock=False,
    )
    _no_pipeline(service)

    import app.core.training.runtime_stats as stats_mod
    import app.core.training.sft as sft_mod

    monkeypatch.setattr(sft_mod, "training_deps_available", lambda: True)

    class _FakeTorch:
        class cuda:  # noqa: N801 - must mirror torch.cuda attribute name
            @staticmethod
            def is_available() -> bool:
                return False

    monkeypatch.setitem(__import__("sys").modules, "torch", _FakeTorch)
    monkeypatch.setattr(
        stats_mod,
        "get_runtime_stats",
        lambda: {
            "memory_available_mb": 100.0,
            "cpu_percent": 0.0,
            "memory_total_mb": 0.0,
            "memory_used_mb": 0.0,
        },
    )

    request = CreateTrainingTaskRequest(
        name="low-mem",
        dataset_id="dataset_any",
        config=TrainingConfig(use_mock=False),
    )
    with pytest.raises(ValueError, match="8192"):
        await service.create_task(request)


@pytest.mark.asyncio
async def test_create_task_applies_cpu_smoke_clamp(tmp_path: Path, monkeypatch) -> None:
    sqlite_path = str(tmp_path / "guards.db")
    await init_db(sqlite_path)
    dataset_id = await _seed_dataset(sqlite_path, tmp_path)

    service = TrainingService(
        sqlite_path=sqlite_path,
        data_dir=str(tmp_path),
        models_dir=str(tmp_path / "models"),
        training_use_mock=False,
    )
    _no_pipeline(service)

    import app.core.training.runtime_stats as stats_mod
    import app.core.training.sft as sft_mod

    monkeypatch.setattr(sft_mod, "training_deps_available", lambda: True)

    class _FakeTorch:
        class cuda:  # noqa: N801 - must mirror torch.cuda attribute name
            @staticmethod
            def is_available() -> bool:
                return False

    monkeypatch.setitem(__import__("sys").modules, "torch", _FakeTorch)
    monkeypatch.setattr(
        stats_mod,
        "get_runtime_stats",
        lambda: {
            "memory_available_mb": 16384.0,
            "cpu_percent": 0.0,
            "memory_total_mb": 0.0,
            "memory_used_mb": 0.0,
        },
    )

    request = CreateTrainingTaskRequest(
        name="cpu-smoke",
        dataset_id=dataset_id,
        base_model="Qwen/Qwen2.5-1.5B",
        config=TrainingConfig(use_mock=False, batch_size=8, num_epochs=3),
    )
    task = await service.create_task(request)
    cfg = task["config"]
    assert cfg["use_mock"] is False
    assert cfg["cpu_smoke"] is True
    assert cfg["batch_size"] == 1
    assert cfg["max_steps"] <= 20
    assert cfg["max_samples"] <= 32
    assert cfg["gradient_checkpointing"] is True
    # cancel flag registered for the task
    assert task["id"] in service._cancel_flags
    assert service._cancel_flags[task["id"]] == {"cancel": False}


@pytest.mark.asyncio
async def test_create_task_mock_path_unchanged(tmp_path: Path, monkeypatch) -> None:
    sqlite_path = str(tmp_path / "guards.db")
    await init_db(sqlite_path)
    dataset_id = await _seed_dataset(sqlite_path, tmp_path)

    service = TrainingService(
        sqlite_path=sqlite_path,
        data_dir=str(tmp_path),
        models_dir=str(tmp_path / "models"),
        training_use_mock=True,
    )
    _no_pipeline(service)

    # Guards must NOT fire on mock path: leave real get_runtime_stats intact.
    request = CreateTrainingTaskRequest(
        name="mock-run",
        dataset_id=dataset_id,
        config=TrainingConfig(use_mock=True, batch_size=8),
    )
    task = await service.create_task(request)
    assert task["config"]["use_mock"] is True
    # cpu_smoke clamp must not be applied on mock path
    assert task["config"].get("cpu_smoke") is not True
    assert task["config"]["batch_size"] == 8
    assert task["id"] in service._cancel_flags


@pytest.mark.asyncio
async def test_cancel_task_sets_flag_and_cancels(tmp_path: Path) -> None:
    sqlite_path = str(tmp_path / "guards.db")
    await init_db(sqlite_path)
    dataset_id = await _seed_dataset(sqlite_path, tmp_path)

    service = TrainingService(
        sqlite_path=sqlite_path,
        data_dir=str(tmp_path),
        models_dir=str(tmp_path / "models"),
        training_use_mock=True,
    )

    # Replace pipeline with a long sleep so we can cancel mid-flight.
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

    request = CreateTrainingTaskRequest(
        name="cancel-me",
        dataset_id=dataset_id,
        config=TrainingConfig(use_mock=True),
    )
    task = await service.create_task(request)
    task_id = task["id"]

    # Give the bg task a tick to start.
    await asyncio.sleep(0)
    result = await service.cancel_task(task_id)

    assert service._cancel_flags[task_id]["cancel"] is True
    assert result["status"] == "cancelled"
    bg = service._running_tasks.get(task_id)
    if bg is not None and not bg.done():
        with suppress(asyncio.CancelledError, asyncio.TimeoutError):
            await asyncio.wait_for(bg, timeout=5)
    assert bg is None or bg.done()


@pytest.mark.asyncio
async def test_export_model_rejects_mock_placeholder(tmp_path: Path) -> None:
    sqlite_path = str(tmp_path / "guards.db")
    await init_db(sqlite_path)
    dataset_id = await _seed_dataset(sqlite_path, tmp_path)

    service = TrainingService(
        sqlite_path=sqlite_path,
        data_dir=str(tmp_path),
        models_dir=str(tmp_path / "models"),
        training_use_mock=True,
    )
    _no_pipeline(service)

    request = CreateTrainingTaskRequest(
        name="mock-export",
        dataset_id=dataset_id,
        config=TrainingConfig(use_mock=True),
    )
    task = await service.create_task(request)
    task_id = task["id"]

    # Simulate a completed mock run that produced model.bin.
    async with aiosqlite.connect(sqlite_path) as db:
        db.row_factory = aiosqlite.Row
        from app.repositories.training_repo import TrainingTaskRepository

        repo = TrainingTaskRepository(db)
        await repo.update_status(
            task_id,
            "completed",
            progress=1.0,
            model_path=str(Path(tmp_path / "models" / task_id / "model.bin")),
            result={"mock": True},
            finished_at=datetime.now(tz=UTC).isoformat(),
        )

    with pytest.raises(ValueError, match="Mock model cannot export"):
        await service.export_model(task_id)
