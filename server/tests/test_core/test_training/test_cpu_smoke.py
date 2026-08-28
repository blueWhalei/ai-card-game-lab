import pytest

from app.core.training.cpu_smoke import (
    MIN_AVAILABLE_MEMORY_MB,
    assert_memory_available_for_smoke,
    clamp_cpu_smoke_config,
)


def test_clamp_forces_smoke_limits() -> None:
    out = clamp_cpu_smoke_config(
        {"batch_size": 8, "num_epochs": 3, "max_steps": 999, "max_seq_length": 2048},
        base_model="Qwen/Qwen2.5-1.5B",
    )
    assert out["batch_size"] == 1
    assert out["max_steps"] <= 20
    assert out["max_samples"] <= 32
    assert out["gradient_checkpointing"] is True
    assert out["cpu_smoke"] is True


def test_memory_guard_rejects_low_ram() -> None:
    with pytest.raises(ValueError, match="8"):
        assert_memory_available_for_smoke(MIN_AVAILABLE_MEMORY_MB - 1)
