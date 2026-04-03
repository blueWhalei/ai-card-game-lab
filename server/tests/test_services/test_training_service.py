from __future__ import annotations

from pathlib import Path

import pytest

from app.core.training.exporter import export_sft_dataset
from app.database import init_db
from app.schemas.training import CreateTrainingTaskRequest, TrainingConfig
from app.services.training_service import TrainingService
from app.utils.exceptions import DatasetNotFoundError


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
