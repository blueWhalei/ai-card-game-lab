"""Finite-sample paired inference and orientation of the four binary cells."""

from math import comb

import pytest

from app.core.stats.paired import (
    mcnemar_exact_p,
    paired_difference_interval,
    summarize_paired_outcomes,
)


def test_four_cells_and_mcnemar() -> None:
    result = summarize_paired_outcomes(
        [(True, True), (True, False), (False, False)] + [(False, True)] * 4
    )
    assert result["outcome_counts"] == {
        "both_won": 1,
        "a_only_won": 1,
        "b_only_won": 4,
        "both_lost": 1,
    }
    assert result["win_rate_diff"] == round(3 / 7, 4)
    assert result["paired_p"] == pytest.approx(2 * (1 + 5) / 32)
    assert mcnemar_exact_p(0, 0) == mcnemar_exact_p(5, 5) == 1.0
    assert mcnemar_exact_p(600, 602) == pytest.approx(1 - comb(1202, 601) / 2**1202)


@pytest.mark.parametrize("n", [1, 2, 5, 20, 50])
def test_constant_pairs_retain_sampling_uncertainty(n: int) -> None:
    # At zero events the one-sided upper bound solves (1-u)^n = 0.0125.
    q = 0.0125 ** (1 / n)
    assert paired_difference_interval(0, 0, n) == pytest.approx([q - 1, 1 - q])
    assert paired_difference_interval(n, 0, n) == pytest.approx([2 * q - 1, 1])
    assert paired_difference_interval(0, n, n) == pytest.approx([-1, 1 - 2 * q])
    assert summarize_paired_outcomes([(True, True)] * n)["paired_p"] == 1


def test_empty_pairs_have_no_estimate_or_inference() -> None:
    result = summarize_paired_outcomes([])
    assert not any(result["outcome_counts"].values())
    assert result["win_rate_diff"] is result["paired_ci"] is result["paired_p"] is None


def test_small_sample_coverage_by_direct_trinomial_enumeration() -> None:
    n = 8
    for p_b, p_a in [(0.0, 0.0), (0.01, 0.04), (0.2, 0.5), (0.75, 0.25), (1.0, 0.0)]:
        coverage = 0.0
        for b in range(n + 1):
            for a in range(n - b + 1):
                interval = paired_difference_interval(b, a, n)
                assert interval is not None
                if interval[0] <= p_b - p_a <= interval[1]:
                    coverage += (
                        comb(n, b)
                        * comb(n - b, a)
                        * p_b**b
                        * p_a**a
                        * (1 - p_b - p_a) ** (n - b - a)
                    )
        assert coverage >= 0.95
