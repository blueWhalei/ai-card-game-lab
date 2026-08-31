"""Wilson score interval for binomial proportions."""

from app.core.stats.proportion import wilson_interval


def test_wilson_empty_sample_is_zero_interval() -> None:
    low, high = wilson_interval(0, 0)
    assert low == 0.0
    assert high == 0.0


def test_wilson_eight_of_ten() -> None:
    low, high = wilson_interval(8, 10)
    assert round(low, 3) == 0.490
    assert round(high, 3) == 0.943


def test_wilson_clamps_to_unit_interval() -> None:
    low, high = wilson_interval(10, 10)
    assert 0.0 <= low <= 1.0
    assert 0.0 <= high <= 1.0
    assert low < 1.0
    assert high == 1.0
