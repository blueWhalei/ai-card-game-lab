"""Unit tests for paired McNemar / bootstrap helpers."""

from app.core.stats.paired import mcnemar_exact_p, paired_bootstrap_ci


def test_mcnemar_no_discordance_is_one() -> None:
    assert mcnemar_exact_p(0, 0) == 1.0


def test_mcnemar_symmetric_is_one() -> None:
    assert mcnemar_exact_p(5, 5) == 1.0


def test_mcnemar_strong_discordance_is_small() -> None:
    p = mcnemar_exact_p(10, 0)
    assert p < 0.01


def test_bootstrap_ci_reproducible() -> None:
    diffs = [1.0, 1.0, 0.0, -1.0, 1.0]
    a = paired_bootstrap_ci(diffs, n_boot=500, seed=7)
    b = paired_bootstrap_ci(diffs, n_boot=500, seed=7)
    assert a == b
    assert a[0] <= a[1]
