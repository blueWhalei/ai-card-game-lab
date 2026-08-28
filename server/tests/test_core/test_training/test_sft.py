"""Tests for SFT training dispatch (mock path)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.core.training.sft import (
    run_mock_training,
    run_sft_training,
    training_deps_available,
)


@pytest.mark.asyncio
async def test_run_mock_training_reports_progress(tmp_path: Path) -> None:
    progress_vals: list[float] = []

    async def on_progress(progress: float, **kwargs: Any) -> None:
        progress_vals.append(progress)

    result = await run_mock_training(
        task_id="t1",
        sft_data_path=str(tmp_path / "empty.jsonl"),
        config={"num_epochs": 1},
        on_progress=on_progress,
    )
    assert result["mock"] is True
    assert progress_vals
    assert progress_vals[-1] == 1.0


@pytest.mark.asyncio
async def test_run_sft_training_respects_use_mock(tmp_path: Path) -> None:
    out = tmp_path / "out"
    progress_vals: list[float] = []

    async def on_progress(progress: float, **kwargs: Any) -> None:
        progress_vals.append(progress)

    result = await run_sft_training(
        task_id="t2",
        sft_data_path=str(tmp_path / "data.jsonl"),
        base_model="Qwen/Qwen2.5-1.5B",
        output_dir=str(out),
        config={"use_mock": True, "num_epochs": 1},
        on_progress=on_progress,
        default_use_mock=False,
    )
    assert result["mock"] is True
    assert Path(result["adapter_path"]).exists()


@pytest.mark.asyncio
async def test_run_sft_training_real_without_deps_raises(tmp_path: Path) -> None:
    if training_deps_available():
        pytest.skip("training deps installed; cannot assert missing-deps path")

    async def on_progress(progress: float, **kwargs: Any) -> None:
        pass

    with pytest.raises(RuntimeError, match="Training dependencies missing"):
        await run_sft_training(
            task_id="t3",
            sft_data_path=str(tmp_path / "data.jsonl"),
            base_model="Qwen/Qwen2.5-1.5B",
            output_dir=str(tmp_path / "out"),
            config={"use_mock": False},
            on_progress=on_progress,
            default_use_mock=False,
        )
