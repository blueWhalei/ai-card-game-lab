"""Guards + cancel for TrainingService.

Covers:
- create_task refuses when deps missing or RAM < 8GB.
- create_task applies CPU smoke clamps and persists clamped config.
- cancel_task sets the per-task cancel flag and cancels the bg asyncio task.
- export_model refuses a non-adapter file path.
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


def _pass_training_guards(monkeypatch: pytest.MonkeyPatch) -> None:
    """Skip env probes so tests can create tasks without torch/RAM."""
    import app.core.training.sft as sft_mod
    import app.services.training_service as svc_mod

    monkeypatch.setattr(sft_mod, "training_deps_available", lambda: True)
    monkeypatch.setattr(svc_mod, "_probe_cuda_available", lambda: True)


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
    )
    _no_pipeline(service)

    import app.core.training.sft as sft_mod

    monkeypatch.setattr(sft_mod, "training_deps_available", lambda: False)

    request = CreateTrainingTaskRequest(
        name="no-deps",
        dataset_id="dataset_any",
        config=TrainingConfig(),
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
        config=TrainingConfig(),
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
        config=TrainingConfig(batch_size=8, num_epochs=3),
    )
    task = await service.create_task(request)
    cfg = task["config"]
    assert cfg["cpu_smoke"] is True
    assert cfg["batch_size"] == 1
    assert cfg["max_steps"] <= 20
    assert cfg["max_samples"] <= 32
    assert cfg["gradient_checkpointing"] is True
    # cancel flag registered for the task
    assert task["id"] in service._cancel_flags
    assert service._cancel_flags[task["id"]] == {"cancel": False}


@pytest.mark.asyncio
async def test_cancel_task_sets_flag_and_cancels(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sqlite_path = str(tmp_path / "guards.db")
    await init_db(sqlite_path)
    dataset_id = await _seed_dataset(sqlite_path, tmp_path)

    service = TrainingService(
        sqlite_path=sqlite_path,
        data_dir=str(tmp_path),
        models_dir=str(tmp_path / "models"),
    )
    _pass_training_guards(monkeypatch)

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
        config=TrainingConfig(),
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
async def test_export_model_rejects_non_adapter_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sqlite_path = str(tmp_path / "guards.db")
    await init_db(sqlite_path)
    dataset_id = await _seed_dataset(sqlite_path, tmp_path)

    service = TrainingService(
        sqlite_path=sqlite_path,
        data_dir=str(tmp_path),
        models_dir=str(tmp_path / "models"),
    )
    _pass_training_guards(monkeypatch)
    _no_pipeline(service)

    request = CreateTrainingTaskRequest(
        name="bad-export",
        dataset_id=dataset_id,
        config=TrainingConfig(),
    )
    task = await service.create_task(request)
    task_id = task["id"]

    async with aiosqlite.connect(sqlite_path) as db:
        db.row_factory = aiosqlite.Row
        from app.repositories.training_repo import TrainingTaskRepository

        repo = TrainingTaskRepository(db)
        await repo.update_status(
            task_id,
            "completed",
            progress=1.0,
            model_path=str(Path(tmp_path / "models" / task_id / "model.bin")),
            result={"train_loss": 0.1},
            finished_at=datetime.now(tz=UTC).isoformat(),
        )

    with pytest.raises(ValueError, match="not a LoRA adapter directory"):
        await service.export_model(task_id)


@pytest.mark.asyncio
async def test_cancel_task_refuses_terminal_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """I4: cancel_task must not overwrite a terminal status."""
    sqlite_path = str(tmp_path / "guards.db")
    await init_db(sqlite_path)
    dataset_id = await _seed_dataset(sqlite_path, tmp_path)

    service = TrainingService(
        sqlite_path=sqlite_path,
        data_dir=str(tmp_path),
        models_dir=str(tmp_path / "models"),
    )
    _pass_training_guards(monkeypatch)
    _no_pipeline(service)

    request = CreateTrainingTaskRequest(
        name="terminal",
        dataset_id=dataset_id,
        config=TrainingConfig(),
    )
    task = await service.create_task(request)
    task_id = task["id"]

    # Force the task into each terminal state and assert cancel refuses.
    for terminal in ("completed", "failed", "cancelled"):
        await service._update(task_id, terminal)
        with pytest.raises(ValueError, match="already '"):
            await service.cancel_task(task_id)
        # Status preserved.
        refreshed = await service.get_task(task_id)
        assert refreshed["status"] == terminal


@pytest.mark.asyncio
async def test_create_task_rejects_qlora_without_cuda(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sqlite_path = str(tmp_path / "guards.db")
    await init_db(sqlite_path)
    dataset_id = await _seed_dataset(sqlite_path, tmp_path)

    service = TrainingService(
        sqlite_path=sqlite_path,
        data_dir=str(tmp_path),
        models_dir=str(tmp_path / "models"),
    )
    _no_pipeline(service)

    import app.core.training.sft as sft_mod
    import app.services.training_service as svc_mod

    monkeypatch.setattr(sft_mod, "training_deps_available", lambda: True)
    monkeypatch.setattr(svc_mod, "_probe_cuda_available", lambda: False)

    request = CreateTrainingTaskRequest(
        name="qlora-cpu",
        dataset_id=dataset_id,
        config=TrainingConfig(qlora=True),
    )
    with pytest.raises(ValueError, match="NVIDIA GPU"):
        await service.create_task(request)


@pytest.mark.asyncio
async def test_create_task_rejects_qlora_without_bitsandbytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sqlite_path = str(tmp_path / "guards.db")
    await init_db(sqlite_path)
    dataset_id = await _seed_dataset(sqlite_path, tmp_path)

    service = TrainingService(
        sqlite_path=sqlite_path,
        data_dir=str(tmp_path),
        models_dir=str(tmp_path / "models"),
    )
    _no_pipeline(service)

    import app.core.training.sft as sft_mod

    _pass_training_guards(monkeypatch)
    monkeypatch.setattr(sft_mod, "bitsandbytes_available", lambda: False)

    request = CreateTrainingTaskRequest(
        name="qlora-no-bnb",
        dataset_id=dataset_id,
        config=TrainingConfig(qlora=True),
    )
    with pytest.raises(ValueError, match="bitsandbytes"):
        await service.create_task(request)


@pytest.mark.asyncio
async def test_create_task_persists_qlora_on_cuda(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sqlite_path = str(tmp_path / "guards.db")
    await init_db(sqlite_path)
    dataset_id = await _seed_dataset(sqlite_path, tmp_path)

    service = TrainingService(
        sqlite_path=sqlite_path,
        data_dir=str(tmp_path),
        models_dir=str(tmp_path / "models"),
    )
    _pass_training_guards(monkeypatch)
    _no_pipeline(service)

    import app.core.training.sft as sft_mod

    monkeypatch.setattr(sft_mod, "bitsandbytes_available", lambda: True)

    request = CreateTrainingTaskRequest(
        name="qlora-ok",
        dataset_id=dataset_id,
        config=TrainingConfig(qlora=True, batch_size=8),
    )
    task = await service.create_task(request)
    cfg = task["config"]
    assert cfg["qlora"] is True
    assert cfg.get("cpu_smoke") is not True
    assert cfg["batch_size"] == 8


@pytest.mark.asyncio
async def test_apply_cpu_smoke_guards_runs_probes_off_event_loop(
    tmp_path: Path, monkeypatch
) -> None:
    """I2: heavy probes must run via asyncio.to_thread, not inline on the loop."""
    sqlite_path = str(tmp_path / "guards.db")
    await init_db(sqlite_path)

    service = TrainingService(
        sqlite_path=sqlite_path,
        data_dir=str(tmp_path),
        models_dir=str(tmp_path / "models"),
    )

    import app.core.training.runtime_stats as stats_mod
    import app.core.training.sft as sft_mod
    import app.services.training_service as svc_mod

    monkeypatch.setattr(sft_mod, "training_deps_available", lambda: True)

    class _FakeTorch:
        class cuda:  # noqa: N801
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

    # Track whether probes were dispatched to a worker thread.
    real_to_thread = asyncio.to_thread
    expected_funcs = {
        sft_mod.training_deps_available,
        svc_mod._probe_cuda_available,
        stats_mod.get_runtime_stats,
    }
    seen_funcs: list[Any] = []

    async def _spy_to_thread(func, *args, **kwargs):
        if func in expected_funcs:
            seen_funcs.append(func)
        return await real_to_thread(func, *args, **kwargs)

    monkeypatch.setattr(svc_mod.asyncio, "to_thread", _spy_to_thread)

    cfg = await service._apply_cpu_smoke_guards(
        {"batch_size": 8, "num_epochs": 3, "max_steps": 999},
        base_model="Qwen/Qwen2.5-0.5B",
    )
    assert cfg["cpu_smoke"] is True
    assert cfg["batch_size"] == 1
    # All three heavy probes must have run off the event loop.
    assert set(seen_funcs) == expected_funcs
