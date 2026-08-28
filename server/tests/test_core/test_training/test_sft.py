"""Tests for SFT training dispatch (mock path)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.core.training.sft import (
    run_mock_training,
    run_sft_training,
    should_cancel,
    training_deps_available,
    truncate_texts,
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


def test_truncate_texts_caps_to_max_samples() -> None:
    texts = ["a", "b", "c", "d", "e"]
    assert truncate_texts(texts, 2) == ["a", "b"]
    assert truncate_texts(texts, 0) == texts
    assert truncate_texts(texts, None) == texts
    assert truncate_texts(texts, -1) == texts
    assert truncate_texts(texts, 100) == texts


def test_truncate_texts_preserves_order_and_identity() -> None:
    texts = ["x1", "x2", "x3"]
    out = truncate_texts(texts, 2)
    assert out == texts[:2]
    # No mutation of the input list
    assert texts == ["x1", "x2", "x3"]


def test_should_cancel_returns_false_for_none() -> None:
    assert should_cancel(None) is False


def test_should_cancel_returns_false_when_flag_not_set() -> None:
    assert should_cancel({"cancel": False}) is False
    assert should_cancel({}) is False


def test_should_cancel_returns_true_when_flag_set() -> None:
    assert should_cancel({"cancel": True}) is True


def test_cancel_callback_sets_stop_when_flag_set() -> None:
    """Lightweight test of the cancel callback behavior without HF deps.

    Re-implements the same one-liner the nested ``_CancelCallback`` uses so we
    can assert the contract without importing transformers. The real callback
    delegates to ``should_cancel`` and sets ``control.should_training_stop``.
    """

    class _FakeControl:
        should_training_stop: bool = False

    class _FakeCancelCallback:
        def __init__(self, cancel_flag: dict[str, bool] | None) -> None:
            self._flag = cancel_flag

        def on_step_end(self, control: _FakeControl) -> _FakeControl:
            if should_cancel(self._flag):
                control.should_training_stop = True
            return control

    control = _FakeControl()
    cb = _FakeCancelCallback({"cancel": True})
    cb.on_step_end(control)
    assert control.should_training_stop is True

    control2 = _FakeControl()
    cb2 = _FakeCancelCallback({"cancel": False})
    cb2.on_step_end(control2)
    assert control2.should_training_stop is False


def test_load_chatml_respects_max_samples(tmp_path: Path) -> None:
    """End-to-end check that truncate_texts caps a real ChatML JSONL load.

    Writes 5 ChatML records, then truncates the loaded texts to 2 via the
    public ``truncate_texts`` helper (the same call ``_run_lora_sft_sync``
    makes after ``_load_chatml_texts``).
    """
    from app.core.training.sft import _load_chatml_texts

    data_path = tmp_path / "data.jsonl"
    records = [{"messages": [{"role": "user", "content": str(i)}]} for i in range(5)]
    data_path.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")

    class _StubTokenizer:
        def apply_chat_template(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
            return "\n".join(f"{m['role']}: {m['content']}" for m in messages)

    texts = _load_chatml_texts(str(data_path), _StubTokenizer())
    assert len(texts) == 5
    capped = truncate_texts(texts, 2)
    assert len(capped) == 2
    assert capped == texts[:2]
