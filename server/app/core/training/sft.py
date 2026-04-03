"""Mock SFT trainer — simulates training progress for development.

Walks through the state machine (exporting → training → completed)
with simulated progress updates. Replace with real training logic
(e.g. Hugging Face Trainer, LoRA) when ready for production.
"""

from __future__ import annotations

import asyncio
from typing import Any, Protocol

import structlog

logger = structlog.get_logger()

MOCK_STEPS = 20
MOCK_STEP_DELAY = 1.5  # seconds per step


class ProgressCallback(Protocol):
    """Callback to report training progress."""

    async def __call__(self, progress: float, **kwargs: Any) -> None: ...


async def run_mock_training(
    task_id: str,
    sft_data_path: str,
    config: dict[str, Any],
    on_progress: ProgressCallback,
) -> dict[str, Any]:
    """Simulate an SFT training run.

    Args:
        task_id: The training task ID.
        sft_data_path: Path to the exported SFT JSONL.
        config: Training hyperparameters (learning_rate, batch_size, etc.).
        on_progress: Async callback invoked with progress 0.0–1.0.

    Returns:
        A result dict with mock metrics.
    """
    logger.info("mock_training_start", task_id=task_id, config=config)

    for step in range(1, MOCK_STEPS + 1):
        await asyncio.sleep(MOCK_STEP_DELAY)
        progress = step / MOCK_STEPS
        await on_progress(progress, step=step, total_steps=MOCK_STEPS)
        logger.debug("mock_training_step", task_id=task_id, step=step, progress=progress)

    result = {
        "train_loss": 0.42,
        "eval_loss": 0.51,
        "total_steps": MOCK_STEPS,
        "epochs": config.get("num_epochs", 3),
        "mock": True,
    }
    logger.info("mock_training_done", task_id=task_id, result=result)
    return result
