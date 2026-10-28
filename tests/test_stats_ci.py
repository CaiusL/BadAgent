"""Tests for guard.stats_ci — exact binomial intervals."""
import pytest

from guard import stats_ci


def test_zero_count_exact_upper_bound():
    """Exact CP upper bound for 0/30 is 1 - (0.025)^(1/30) = 0.1157."""
    lo, hi = stats_ci.clopper_pearson(0, 30)
    assert lo == 0.0
    assert abs(hi - (1 - 0.025 ** (1 / 30))) < 1e-9


def test_zero_count_reports_rule_of_three_separately():
    """The rule of three (3/n) is an approximation, not the exact bound.

    Both are reported so a reader can see the exact interval and the
    commonly quoted bound agree in order of magnitude.
    """
    r = stats_ci.rate(0, 30)
    assert abs(r["rule_of_three_upper"] - 3 / 30) < 1e-9
    assert abs(r["hi"] - 0.1157) < 5e-4
    assert r["hi"] > r["rule_of_three_upper"]


def test_all_successes_bounds():
    lo, hi = stats_ci.clopper_pearson(30, 30)
    assert hi == 1.0
    assert 0.0 < lo < 1.0


def test_interval_contains_point_estimate():
    for k, n in ((1, 10), (5, 30), (34, 34), (9, 272), (6, 79)):
        lo, hi = stats_ci.clopper_pearson(k, n)
        assert lo <= k / n <= hi


def test_symmetry_of_off_by_one():
    """CP(k, n) upper == 1 - CP(n-k, n) lower, by construction."""
    lo1, hi1 = stats_ci.clopper_pearson(3, 20)
    lo2, hi2 = stats_ci.clopper_pearson(17, 20)
    assert abs(hi1 - (1 - lo2)) < 1e-6
    assert abs(lo1 - (1 - hi2)) < 1e-6


def test_interval_narrows_with_n():
    lo1, hi1 = stats_ci.clopper_pearson(5, 10)
    lo2, hi2 = stats_ci.clopper_pearson(50, 100)
    assert (hi2 - lo2) < (hi1 - lo1)


def test_rate_returns_count_and_denominator():
    r = stats_ci.rate(9, 272)
    assert r["k"] == 9 and r["n"] == 272
    assert set(r) >= {"k", "n", "rate", "lo", "hi"}


def test_rate_zero_denominator():
    r = stats_ci.rate(0, 0)
    assert r["n"] == 0


def test_fmt_rate_includes_counts_and_interval():
    text = stats_ci.fmt_rate(stats_ci.rate(9, 272))
    assert "9/272" in text
    assert "%" in text


def test_known_value_matches_published_table():
    """CP 95% for 1/10 is (0.0025, 0.4450) to 4 dp."""
    lo, hi = stats_ci.clopper_pearson(1, 10)
    assert abs(lo - 0.0025) < 5e-4
    assert abs(hi - 0.4450) < 5e-4