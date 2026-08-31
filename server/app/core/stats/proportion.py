"""Binomial proportion confidence intervals."""

from __future__ import annotations

import math


def wilson_interval(
    successes: int,
    n: int,
    *,
    z: float = 1.96,
) -> tuple[float, float]:
    """Return a Wilson score interval for a binomial proportion.

    ``successes`` / ``n`` is the observed rate. When ``n`` is 0 the interval
    is ``(0.0, 0.0)``. Bounds are clamped to ``[0, 1]``.
    """
    if n <= 0:
        return (0.0, 0.0)
    if successes < 0:
        successes = 0
    if successes > n:
        successes = n

    p = successes / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (p + z2 / (2.0 * n)) / denom
    margin = z * math.sqrt((p * (1.0 - p) + z2 / (4.0 * n)) / n) / denom
    low = max(0.0, center - margin)
    high = min(1.0, center + margin)
    return (low, high)
