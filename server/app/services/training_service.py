"""Training task management service.

Orchestrates the full lifecycle: create → export → train → complete/fail.
"""

from __future__ import annotations

import asyncio
import json
import re
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog

from app.config import Settings
from app.core.training.deploy import export_deploy_bundle
from app.core.training.exporter import export_sft_dataset
from app.core.training.sft import run_sft_training
from app.core.training.verify import ollama_list_tags, ollama_smoke_decision
from app.database import open_db_connection
from app.repositories.dataset_repo import DatasetRepository
from app.repositories.training_repo import TrainingTaskRepository
from app.schemas.training import CreateTrainingTaskRequest
from app.utils.exceptions import DatasetNotFoundError, TrainingTaskNotFoundError
from app.utils.id_generator import generate_id

logger = structlog.get_logger()

# Terminal states that cancel_task must not overwrite.
_TERMINAL_STATUSES: frozenset[str] = frozenset(
    {"completed", "failed", "cancelled"}
)


def _count_jsonl_lines(path: str) -> int:
    """Count non-empty lines in a JSONL file (best-effort sample count)."""
    p = Path(path)
    if not p.exists():
        return 0
    count = 0
    with p.open("r", encoding="utf-8") as fin:
        for line in fin:
            if line.strip():
                count += 1
    return count
_ACTIVE_STATUSES: frozenset[str] = frozenset({"pending", "exporting", "training"})


def _probe_cuda_available() -> bool:
    """Return True if a CUDA GPU is available to torch.

    Imported lazily and executed in a worker thread by the guards so the
    event loop is never blocked by the (slow) first torch import.
    """
    try:
        import torch

        return bool(torch.cuda.is_available())
    except ImportError:
        # deps check passed but torch import failed — treat as CPU smoke.
        return False


class TrainingService:
    """Manages training task lifecycle."""

    def __init__(
        self,
        sqlite_path: str,
        data_dir: str,
        models_dir: str,
        *,
        training_use_mock: bool = True,
        ollama_base_url: str = "http://localhost:11434",
    ) -> None:
        self._sqlite_path = sqlite_path
        self._data_dir = data_dir
        self._models_dir = models_dir
        self._training_use_mock = training_use_mock
        self._ollama_base_url = ollama_base_url
        self._running_tasks: dict[str, asyncio.Task[None]] = {}
        self._cancel_flags: dict[str, dict[str, bool]] = {}

    @classmethod
    def from_settings(cls, settings: Settings) -> TrainingService:
        return cls(
            sqlite_path=settings.sqlite_path,
            data_dir=settings.data_dir,
            models_dir=settings.models_dir,
            training_use_mock=settings.training_use_mock,
            ollama_base_url=settings.ollama_base_url,
        )

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
            try:
                return await repo.get_by_id(task_id)
            except KeyError as exc:
                raise TrainingTaskNotFoundError(task_id) from exc

    async def create_task(self, request: CreateTrainingTaskRequest) -> dict[str, Any]:
        """Create a training task and kick off the background pipeline."""
        task_id = generate_id("train")
        now = datetime.now(tz=timezone.utc).isoformat()

        # ── Guards: resolve use_mock, then enforce CPU smoke safety ──
        cfg = dict(request.config.model_dump())
        use_mock = cfg.get("use_mock")
        if use_mock is None:
            use_mock = self._training_use_mock
        if use_mock:
            cfg["use_mock"] = True
        else:
            cfg = await self._apply_cpu_smoke_guards(cfg, base_model=request.base_model)
            cfg["use_mock"] = False

        # Validate dataset exists
        async with self._get_bg_db() as db:
            ds_repo = DatasetRepository(db)
            try:
                dataset = await ds_repo.get_by_id(request.dataset_id)
            except KeyError as exc:
                raise DatasetNotFoundError(request.dataset_id) from exc

        # Per-task cancel flag, threaded into the LoRA path so cancel_task
        # can cooperatively interrupt the Trainer loop.
        cancel_flag: dict[str, bool] = {"cancel": False}
        self._cancel_flags[task_id] = cancel_flag

        # Persist task with the (possibly clamped) config
        async with self._get_bg_db() as db:
            repo = TrainingTaskRepository(db)
            task = await repo.create(
                {
                    "id": task_id,
                    "name": request.name,
                    "dataset_id": request.dataset_id,
                    "base_model": request.base_model,
                    "training_type": request.training_type,
                    "config": cfg,
                    "status": "pending",
                    "progress": 0,
                    "created_at": now,
                }
            )

        # Launch background pipeline
        bg = asyncio.create_task(self._run_pipeline(task_id, dataset, cancel_flag))
        self._running_tasks[task_id] = bg
        return task

    async def _apply_cpu_smoke_guards(
        self, cfg: dict[str, Any], *, base_model: str
    ) -> dict[str, Any]:
        """Enforce non-mock CPU safety: deps present, RAM ≥ 8GB, clamped config.

        Heavy probes (``training_deps_available`` + ``torch.cuda.is_available``)
        run off the event loop via ``asyncio.to_thread`` so concurrent requests
        are not blocked. Raises ``ValueError`` (mapped to HTTP 400 by the API
        layer) when the environment is unsafe. Returns the (possibly clamped)
        config dict.
        """
        from app.core.training.sft import training_deps_available

        deps_ok = await asyncio.to_thread(training_deps_available)
        if not deps_ok:
            raise ValueError("Training deps missing: poetry install --with training")

        cuda = await asyncio.to_thread(_probe_cuda_available)

        if not cuda:
            from app.core.training.cpu_smoke import (
                assert_memory_available_for_smoke,
                clamp_cpu_smoke_config,
            )
            from app.core.training.runtime_stats import get_runtime_stats

            stats = await asyncio.to_thread(get_runtime_stats)
            assert_memory_available_for_smoke(float(stats["memory_available_mb"]))
            cfg = clamp_cpu_smoke_config(cfg, base_model=base_model)
            # still allow non-whitelist base_model but keep clamps; FE already warned
        return cfg

    async def cancel_task(self, task_id: str) -> dict[str, Any]:
        """Cooperatively cancel a running training task.

        Only transitions tasks in active states (``pending``, ``exporting``,
        ``training``). For terminal states (``completed``, ``failed``,
        ``cancelled``) raises ``ValueError`` so the API layer returns 400
        instead of overwriting the terminal status.

        Sets the per-task cancel flag (the LoRA Trainer loop checks it each
        step) and cancels the background asyncio task. Then marks the task
        ``cancelled`` in the DB and returns the refreshed task row.
        """
        current = await self.get_task(task_id)
        status = str(current.get("status") or "")
        if status in _TERMINAL_STATUSES:
            raise ValueError(
                f"Task {task_id} is already '{status}'; cannot cancel a terminal task"
            )
        if status not in _ACTIVE_STATUSES:
            raise ValueError(
                f"Task {task_id} has unknown status '{status}'; expected one of "
                f"{sorted(_ACTIVE_STATUSES)}"
            )

        flag = self._cancel_flags.get(task_id)
        if flag is not None:
            flag["cancel"] = True
        bg = self._running_tasks.get(task_id)
        if bg and not bg.done():
            bg.cancel()
        await self._update(task_id, "cancelled")
        return await self.get_task(task_id)

    async def delete_task(self, task_id: str) -> None:
        # Cancel if running
        bg = self._running_tasks.pop(task_id, None)
        if bg and not bg.done():
            bg.cancel()
        self._cancel_flags.pop(task_id, None)
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

    async def export_model(
        self,
        model_id: str,
        *,
        ollama_tag: str | None = None,
        merge: bool = True,
        try_create: bool = False,
    ) -> dict[str, Any]:
        """Export LoRA adapter to a deploy bundle (merged HF + Modelfile + GGUF scripts)."""
        task = await self.get_task(model_id)
        model_path = task.get("model_path")
        if not model_path:
            raise ValueError("Task has no model_path; train to completion first")
        if task.get("status") != "completed":
            raise ValueError(f"Task status is {task.get('status')}, expected completed")
        # Refuse mock placeholders: a mock run writes model.bin and never
        # produces a real LoRA adapter directory, so there is nothing to merge
        # or quantize into a deploy bundle.
        result = task.get("result")
        is_mock = (
            str(model_path).endswith("model.bin")
            or (isinstance(result, dict) and result.get("mock"))
            or not Path(str(model_path)).is_dir()
        )
        if is_mock:
            raise ValueError(
                "Mock model cannot export deploy bundle; run CPU smoke or GPU LoRA first"
            )

        return await asyncio.to_thread(
            export_deploy_bundle,
            task_id=model_id,
            model_path=str(model_path),
            base_model=str(task.get("base_model") or "Qwen/Qwen2.5-1.5B"),
            models_dir=self._models_dir,
            ollama_tag=ollama_tag,
            merge=merge,
            try_create=try_create,
        )

    async def verify_model(
        self,
        model_id: str,
        *,
        ollama_tag: str | None = None,
        run_game: bool = False,
        player_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Verify a deployed Ollama model with a decision smoke test (optional full game)."""
        await self.get_task(model_id)

        tag = ollama_tag
        if not tag:
            meta_path = Path(self._models_dir) / model_id / "deploy" / "export_meta.json"
            if meta_path.is_file():
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                tag = str(meta.get("ollama_tag") or "")
            if not tag:
                tag = f"acgl-{model_id[:12]}"

        result: dict[str, Any] = {
            "model_id": model_id,
            "ollama_tag": tag,
            "ollama_base_url": self._ollama_base_url,
        }

        try:
            tags = await ollama_list_tags(self._ollama_base_url)
        except Exception as exc:
            result["ok"] = False
            result["error"] = f"Cannot reach Ollama: {exc}"
            return result

        result["available_tags"] = tags
        tag_matched = any(t == tag or t.startswith(f"{tag}:") for t in tags)
        if not tag_matched:
            result["ok"] = False
            result["error"] = (
                f"Ollama tag '{tag}' not found. Export GGUF then: "
                f"ollama create {tag} -f models/{model_id}/deploy/Modelfile"
            )
            return result

        smoke = await ollama_smoke_decision(
            base_url=self._ollama_base_url,
            model_name=tag,
        )
        result["smoke"] = smoke
        result["ok"] = bool(smoke.get("ok"))

        if run_game and result["ok"]:
            result["game"] = await self._run_verify_game(
                ollama_tag=tag,
                player_ids=player_ids,
            )
            if result["game"].get("status") not in {"completed", "finished"}:
                result["ok"] = False

        return result

    async def _run_verify_game(
        self,
        *,
        ollama_tag: str,
        player_ids: list[str] | None,
    ) -> dict[str, Any]:
        """Create and start one doudizhu game using three Ollama-backed players."""
        from app.dependencies import get_experiment_config_service, get_game_service

        configs = get_experiment_config_service()
        game_service = get_game_service()

        ids = player_ids or [f"verify_p{i}" for i in range(1, 4)]
        ids = [re.sub(r"[^a-zA-Z0-9_-]", "_", pid)[:40] for pid in ids]

        for i, pid in enumerate(ids):
            model_config = {
                "provider": "ollama",
                "model_name": ollama_tag,
                "temperature": 0.3,
                "top_p": 0.9,
                "max_tokens": 256,
            }
            existing = configs.get_config(pid)
            if existing is None:
                await configs.create_config(
                    {
                        "id": pid,
                        "name": f"Verify-{i + 1}",
                        "notes": "",
                        "model_config": model_config,
                    }
                )
            else:
                await configs.update_config(pid, {"model_config": model_config})

        game = await game_service.create_game(
            game_type="doudizhu",
            player_ids=ids,
        )
        game_id = str(game["id"])
        await game_service.start_game(game_id)

        deadline = asyncio.get_event_loop().time() + 600
        last: dict[str, Any] = {}
        while asyncio.get_event_loop().time() < deadline:
            last = await game_service.get_game(game_id)
            status = str(last.get("status") or "")
            if status in {"completed", "finished", "failed", "cancelled", "error"}:
                break
            await asyncio.sleep(2)

        return {
            "game_id": game_id,
            "player_ids": ids,
            "status": last.get("status"),
            "winner_id": last.get("winner_id"),
            "total_rounds": last.get("total_rounds"),
        }

    # ── Background pipeline ──────────────────────────────

    async def _run_pipeline(
        self,
        task_id: str,
        dataset: dict[str, Any],
        cancel_flag: dict[str, bool] | None = None,
    ) -> None:
        """Background: export → train → complete."""
        try:
            # Phase 1: Export (or use pre-built ChatML from decisions)
            await self._update(task_id, "exporting", progress=0.0)
            source_path = str(Path(self._data_dir) / dataset["file_path"])
            filters = dataset.get("filters") or {}
            if isinstance(filters, str):
                try:
                    filters = json.loads(filters)
                except json.JSONDecodeError:
                    filters = {}
            is_chatml = isinstance(filters, dict) and filters.get("format") == "chatml"
            if is_chatml:
                sft_path = source_path
                sample_count = int(dataset.get("sample_count") or 0)
                if sample_count <= 0:
                    # Count lines if DB count missing
                    sample_count = await asyncio.to_thread(_count_jsonl_lines, sft_path)
                logger.info(
                    "pipeline_chatml_dataset",
                    task_id=task_id,
                    samples=sample_count,
                    path=sft_path,
                )
            else:
                sft_path = str(Path(self._data_dir) / "datasets" / f"{task_id}_sft.jsonl")
                sample_count = await asyncio.to_thread(
                    export_sft_dataset,
                    source_path,
                    sft_path,
                    None,
                    False,  # include_thinking: default off for cleaner BC data
                )
                logger.info("pipeline_export_done", task_id=task_id, samples=sample_count)

            if sample_count == 0:
                await self._update(
                    task_id,
                    "failed",
                    result={"error": "No training samples exported from dataset"},
                )
                return

            # Phase 2: Train (LoRA or mock)
            await self._update(task_id, "training", progress=0.0)
            task_data = await self.get_task(task_id)
            config = dict(task_data.get("config") or {})
            base_model = str(task_data.get("base_model") or "Qwen/Qwen2.5-1.5B")
            model_dir = Path(self._models_dir) / task_id
            model_dir.mkdir(parents=True, exist_ok=True)

            async def on_progress(progress: float, **kw: Any) -> None:
                await self._update(task_id, "training", progress=progress)

            result = await run_sft_training(
                task_id=task_id,
                sft_data_path=sft_path,
                base_model=base_model,
                output_dir=str(model_dir),
                config=config,
                on_progress=on_progress,
                default_use_mock=self._training_use_mock,
                cancel_flag=cancel_flag,
            )

            # Phase 3: Complete — prefer adapter dir for real LoRA
            model_path = str(result.get("adapter_path") or (model_dir / "model.bin"))
            now = datetime.now(tz=timezone.utc).isoformat()
            await self._update(
                task_id,
                "completed",
                progress=1.0,
                model_path=model_path,
                result=result,
                finished_at=now,
            )
        except asyncio.CancelledError:
            await self._update(task_id, "cancelled")
        except Exception as exc:
            logger.exception("pipeline_failed", task_id=task_id)
            await self._update(
                task_id,
                "failed",
                result={"error": str(exc) or "Unexpected error"},
            )
        finally:
            self._running_tasks.pop(task_id, None)
            self._cancel_flags.pop(task_id, None)

    async def _update(self, task_id: str, status: str, **kwargs: Any) -> None:
        """Helper to update task status via a fresh DB connection."""
        async with self._get_bg_db() as db:
            repo = TrainingTaskRepository(db)
            await repo.update_status(task_id, status, **kwargs)
