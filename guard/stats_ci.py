"""
Statistics helpers: Clopper-Pearson intervals and the rule of three.

Every rate in this study is reported as a count with its denominator and a
95% interval. A zero count uses the rule of three: 3/n.
"""

import math


def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction for the incomplete beta function (Lentz)."""
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    d = tiny if abs(d) < tiny else d
    d = 1.0 / d
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = tiny if abs(d) < tiny else d
        c = 1.0 + aa / c
        c = tiny if abs(c) < tiny else c
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = tiny if abs(d) < tiny else d
        c = 1.0 + aa / c
        c = tiny if abs(c) < tiny else c
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-12:
            break
    return h


def _betainc(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(lbeta + a * math.log(x) + b * math.log(1.0 - x))
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def _beta_ppf(p: float, a: float, b: float) -> float:
    """Inverse regularized incomplete beta by bisection."""
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if _betainc(a, b, mid) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def clopper_pearson(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Exact binomial interval for k successes out of n."""
    if n == 0:
        return 0.0, 1.0
    if k == 0:
        return 0.0, 1.0 - (alpha / 2.0) ** (1.0 / n)
    if k == n:
        return (alpha / 2.0) ** (1.0 / n), 1.0
    lower = _beta_ppf(alpha / 2.0, k, n - k + 1)
    upper = _beta_ppf(1.0 - alpha / 2.0, k + 1, n - k)
    return lower, upper


def rate(k: int, n: int) -> dict:
    """Count, denominator, point rate and 95% interval."""
    if n == 0:
        return {"k": k, "n": n, "rate": None, "lo": None, "hi": None,
                "note": "no rows"}
    point = k / n
    lo, hi = clopper_pearson(k, n)
    out = {"k": k, "n": n, "rate": round(point, 4),
           "lo": round(lo, 4), "hi": round(hi, 4)}
    if k == 0:
        out["rule_of_three_upper"] = round(3.0 / n, 4)
    return out


def fmt_rate(r: dict) -> str:
    """One-line rendering: k/n (rate, CI lo-hi)."""
    if r["n"] == 0:
        return "0/0"
    return (f"{r['k']}/{r['n']} ({r['rate']*100:.1f}%, "
            f"95% CI {r['lo']*100:.1f}-{r['hi']*100:.1f}%)")