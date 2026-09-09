"""Paired-experiment statistics (McNemar + bootstrap CI)."""

from __future__ import annotations

import math
import random
from collections.abc import Sequence


def mcnemar_exact_p(b: int, c: int) -> float:
    """Two-sided exact McNemar p-value on discordant counts ``b`` and ``c``.

    Under H0 the smaller count is Binomial(``b + c``, 0.5). Returns 1.0 when
    there are no discordant pairs.
    """
    if b < 0 or c < 0:
        raise ValueError("discordant counts must be non-negative")
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    # Sum P(X <= k) for X ~ Bin(n, 1/2); two-sided by doubling, capped at 1.
    tail = sum(math.comb(n, i) for i in range(k + 1)) / float(2**n)
    return min(1.0, 2.0 * tail)


def paired_bootstrap_ci(
    diffs: Sequence[float],
    *,
    n_boot: int = 2000,
    seed: int = 0,
    alpha: float = 0.05,
) -> tuple[float, float]:
    """Percentile CI for the mean of paired per-seed differences.

    Empty ``diffs`` → ``(0.0, 0.0)``.
    """
    values = [float(x) for x in diffs]
    if not values:
        return (0.0, 0.0)
    rng = random.Random(seed)
    n = len(values)
    means: list[float] = []
    for _ in range(max(1, n_boot)):
        total = 0.0
        for _ in range(n):
            total += values[rng.randrange(n)]
        means.append(total / n)
    means.sort()
    lo_i = math.floor(alpha / 2 * (len(means) - 1))
    hi_i = math.ceil((1 - alpha / 2) * (len(means) - 1))
    hi_i = min(hi_i, len(means) - 1)
    return (round(means[lo_i], 4), round(means[hi_i], 4))
