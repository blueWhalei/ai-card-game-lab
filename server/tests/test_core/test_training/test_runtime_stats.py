from app.core.training.runtime_stats import get_runtime_stats


def test_get_runtime_stats_shape() -> None:
    stats = get_runtime_stats()
    assert "cpu_percent" in stats
    assert stats["memory_total_mb"] > 0
    assert stats["memory_available_mb"] >= 0
    assert stats["memory_used_mb"] >= 0
