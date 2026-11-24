"""Paired binary outcomes, exact McNemar test and conservative difference interval."""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable
from typing import Any


def _binomial_left_tail(k: int, n: int, p: float) -> float:
    """P(X <= k) for k <= n*p and 0 < p < 1. Sum from the largest term down."""
    log_mass = math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)
    mass = math.exp(log_mass + k * math.log(p) + (n - k) * math.log1p(-p))
    total = mass
    for i in range(k, 0, -1):
        mass *= (i / (n - i + 1)) * ((1 - p) / p)
        if total + mass == total:
            break
        total += mass
    return total


def mcnemar_exact_p(b: int, c: int) -> float:
    """Two-sided exact McNemar p-value on discordant counts."""
    if b < 0 or c < 0:
        raise ValueError("discordant counts must be non-negative")
    if abs(b - c) <= 1:
        return 1.0
    return min(1.0, 2 * _binomial_left_tail(min(b, c), b + c, 0.5))


def _upper_binomial_limit(k: int, n: int, tail: float) -> float:
    """One-sided Clopper–Pearson upper bound by inversion of the binomial CDF."""
    if k == n:
        return 1.0
    if k == 0:
        return -math.expm1(math.log(tail) / n)
    low, high = k / n, 1.0
    for _ in range(48):
        mid = (low + high) / 2
        if _binomial_left_tail(k, n, mid) > tail:
            low = mid
        else:
            high = mid
    return high


def paired_difference_interval(b_only: int, a_only: int, n: int) -> list[float] | None:
    """Conservative 95% interval for P(B only) − P(A only); see docs/designs/paired-stats.md."""
    if min(b_only, a_only) < 0 or b_only + a_only > n:
        raise ValueError("invalid paired outcome counts")
    if n == 0:
        return None
    # Two individual 97.5% marginal intervals, each with 1.25% in either tail.
    tail = 0.05 / 4
    lower = 1 - _upper_binomial_limit(n - b_only, n, tail) - _upper_binomial_limit(a_only, n, tail)
    upper = _upper_binomial_limit(b_only, n, tail) - (
        1 - _upper_binomial_limit(n - a_only, n, tail)
    )
    return [lower, upper]


def summarize_paired_outcomes(outcomes: Iterable[tuple[bool, bool]]) -> dict[str, Any]:
    """Each observation is (A won, B won) for one effective seed."""
    cells = Counter(outcomes)
    n = cells.total()
    a_only = cells[True, False]
    b_only = cells[False, True]
    return {
        "outcome_counts": {
            "both_won": cells[True, True],
            "a_only_won": a_only,
            "b_only_won": b_only,
            "both_lost": cells[False, False],
        },
        "win_rate_diff": round((b_only - a_only) / n, 4) if n else None,
        "paired_p": mcnemar_exact_p(b_only, a_only) if n else None,
        "paired_ci": paired_difference_interval(b_only, a_only, n),
        "ci_method": "clopper_pearson_bonferroni",
    }
