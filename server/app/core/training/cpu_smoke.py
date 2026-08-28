from __future__ import annotations

from typing import Any

CPU_SMOKE_BASE_MODELS = [
    "Qwen/Qwen2.5-0.5B",
    "Qwen/Qwen2.5-0.5B-Instruct",
]
DEFAULT_CPU_SMOKE_BASE = "Qwen/Qwen2.5-0.5B"
MIN_AVAILABLE_MEMORY_MB = 8192
MAX_STEPS = 20
MAX_SAMPLES = 32
MAX_SEQ_LENGTH = 256


def clamp_cpu_smoke_config(config: dict[str, Any], *, base_model: str) -> dict[str, Any]:
    out = dict(config)
    out["batch_size"] = 1
    out["num_epochs"] = 1
    out["max_steps"] = min(int(out.get("max_steps") or MAX_STEPS), MAX_STEPS)
    out["max_samples"] = min(int(out.get("max_samples") or MAX_SAMPLES), MAX_SAMPLES)
    out["max_seq_length"] = min(int(out.get("max_seq_length") or MAX_SEQ_LENGTH), MAX_SEQ_LENGTH)
    out["gradient_checkpointing"] = True
    out["cpu_smoke"] = True
    out["suggested_base_model"] = DEFAULT_CPU_SMOKE_BASE
    out["base_model_in_whitelist"] = base_model in CPU_SMOKE_BASE_MODELS
    return out


def assert_memory_available_for_smoke(available_mb: float) -> None:
    if available_mb < MIN_AVAILABLE_MEMORY_MB:
        raise ValueError(
            f"Available memory {available_mb:.0f}MB < {MIN_AVAILABLE_MEMORY_MB}MB; "
            "refuse CPU smoke training to avoid system freeze. Free RAM or use Mock."
        )
