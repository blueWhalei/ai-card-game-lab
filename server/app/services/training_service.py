"""Training task management service.

Orchestrates the full lifecycle: create → export → train → complete/fail.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite
import structlog
from contextlib import asynccontextmanager

from app.core.training.exporter import export_sft_dataset
from app.core.training.sft import run_mock_training
from app.database import open_db_connection
from app.repositories.dataset_repo import DatasetRepository
from app.repositories.training_repo import TrainingTaskRepository
from app.schemas.training import CreateTrainingTaskRequest
from app.utils.exceptions import DatasetNotFoundError
from app.utils.id_generator import generate_id

logger = structlog.get_logger()


class TrainingService:
    """Manages training task lifecycle."""

    def __init__(self, sqlite_path: str, data_dir: str, models_dir: str) -> None:
        self._sqlite_path = sqlite_path
        self._data_dir = data_dir
        self._models_dir = models_dir
        self._running_tasks: dict[str, asyncio.Task[None]] = {}

    @asynccontextmanager
    async def _get_bg_db(self) -> Any:
        db = await open_db_connection(self._sqlite_path)
        try:
            yield db
        finally:
            await db.close()

    async def list_tasks(
        self,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        async with self._get_bg_db() as db:
            repo = TrainingTaskRepository(db)
            return await repo.list_all(status=status, page=page, page_size=page_size)

    async def get_task(self, task_id: str) -> dict[str, Any]:
        async with self._get_bg_db() as db:
            repo = TrainingTaskRepository(db)
            return await repo.get_by_id(task_id)

    async def create_task(self, request: CreateTrainingTaskRequest) -> dict[str, Any]:
        """Create a training task and kick off the background pipeline."""
        task_id = generate_id("train")
        now = datetime.now(tz=timezone.utc).isoformat()

        # Validate dataset exists
        async with self._get_bg_db() as db:
            ds_repo = DatasetRepository(db)
            try:
                dataset = await ds_repo.get_by_id(request.dataset_id)
            except KeyError as exc:
                raise DatasetNotFoundError(request.dataset_id) from exc

        # Persist task
        async with self._get_bg_db() as db:
            repo = TrainingTaskRepository(db)
            task = await repo.create({
                "id": task_id,
                "name": request.name,
                "dataset_id": request.dataset_id,
                "base_model": request.base_model,
                "training_type": request.training_type,
                "config": request.config.model_dump(),
                "status": "pending",
                "progress": 0,
                "created_at": now,
            })

        # Launch background pipeline
        bg = asyncio.create_task(self._run_pipeline(task_id, dataset))
        self._running_tasks[task_id] = bg
        return task

    async def delete_task(self, task_id: str) -> None:
        # Cancel if running
        bg = self._running_tasks.pop(task_id, None)
        if bg and not bg.done():
            bg.cancel()
        async with self._get_bg_db() as db:
            repo = TrainingTaskRepository(db)
            await repo.delete(task_id)

    async def list_models(self) -> list[dict[str, Any]]:
        """List completed training tasks that produced a model."""
        async with self._get_bg_db() as db:
            repo = TrainingTaskRepository(db)
            tasks, _ = await repo.list_all(status="completed", page=1, page_size=100)
        return [
            {
                "id": t["id"],
                "name": t["name"],
                "base_model": t["base_model"],
                "training_type": t["training_type"],
                "model_path": t.get("model_path"),
                "created_at": t.get("finished_at") or t["created_at"],
            }
            for t in tasks
            if t.get("model_path")
        ]

    async def delete_model(self, model_id: str) -> None:
        """Clear model_path from a completed task (simulates model deletion)."""
        async with self._get_bg_db() as db:
            repo = TrainingTaskRepository(db)
            await repo.update_status(model_id, "completed", model_path=None)

    # ── Background pipeline ──────────────────────────────

    async def _run_pipeline(self, task_id: str, dataset: dict[str, Any]) -> None:
        """Background: export → train → complete."""
        try:
            # Phase 1: Export
            await self._update(task_id, "exporting", progress=0.0)
            source_path = str(Path(self._data_dir) / dataset["file_path"])
            sft_path = str(Path(self._data_dir) / "datasets" / f"{task_id}_sft.jsonl")
            sample_count = await asyncio.to_thread(
                export_sft_dataset, source_path, sft_path,
            )
            logger.info("pipeline_export_done", task_id=task_id, samples=sample_count)

            if sample_count == 0:
                await self._update(
                    task_id, "failed",
                    result={"error": "No training samples exported from dataset"},
                )
                return

            # Phase 2: Train (mock)
            await self._update(task_id, "training", progress=0.0)
            task_data = await self.get_task(task_id)
            config = task_data.get("config", {})

            async def on_progress(progress: float, **kw: Any) -> None:
                await self._update(task_id, "training", progress=progress)

            result = await run_mock_training(
                task_id=task_id,
                sft_data_path=sft_path,
                config=config,
                on_progress=on_progress,
            )

            # Phase 3: Complete
            model_dir = Path(self._models_dir) / task_id
            model_dir.mkdir(parents=True, exist_ok=True)
            model_path = str(model_dir / "model.bin")
            # Write a placeholder file (non-blocking)
            await asyncio.to_thread(
                (model_dir / "model.bin").write_text, "mock model placeholder"
            )

            now = datetime.now(tz=timezone.utc).isoformat()
            await self._update(
                task_id, "completed",
                progress=1.0,
                model_path=model_path,
                result=result,
                finished_at=now,
            )
        except asyncio.CancelledError:
            await self._update(task_id, "cancelled")
        except Exception:
            logger.exception("pipeline_failed", task_id=task_id)
            await self._update(task_id, "failed", result={"error": "Unexpected error"})
        finally:
            self._running_tasks.pop(task_id, None)

    async def _update(self, task_id: str, status: str, **kwargs: Any) -> None:
        """Helper to update task status via a fresh DB connection."""
        async with self._get_bg_db() as db:
            repo = TrainingTaskRepository(db)
            await repo.update_status(task_id, status, **kwargs)
