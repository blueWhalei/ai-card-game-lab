from __future__ import annotations

from typing import Any

import psutil


def get_runtime_stats() -> dict[str, Any]:
    """Snapshot host CPU and memory for training live panel."""
    vm = psutil.virtual_memory()
    # Non-blocking first call may return 0.0; callers poll repeatedly.
    cpu = float(psutil.cpu_percent(interval=None))
    return {
        "cpu_percent": cpu,
        "memory_total_mb": round(vm.total / (1024 * 1024), 1),
        "memory_used_mb": round(vm.used / (1024 * 1024), 1),
        "memory_available_mb": round(vm.available / (1024 * 1024), 1),
    }
