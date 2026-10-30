"""Decision rules and confusion-matrix metrics.

Rules are pure functions on per-token drops: numbers in, booleans out. They
never see a label, a command string, or a model. That is what keeps the
verdict path free of planted strings and what makes these functions testable
without Metal.

Metrics consume labels, but only after a rule has produced a verdict. No rule
takes a label argument.
"""

from . import config
from .stats_ci import rate


# --- primitives ------------------------------------------------------------
def mean_gap(drops: list[float]) -> float:
    return sum(drops) / len(drops) if drops else 0.0


def max_drop(drops: list[float]) -> float:
    return max(drops) if drops else 0.0


def longest_run(drops: list[float], eps: float) -> int:
    """Longest run of consecutive tokens whose drop stays below eps."""
    best = cur = 0
    for d in drops:
        if d < eps:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def runs_at(drops: list[float],
            epsilons=config.RUN_EPSILONS) -> dict[str, int]:
    """Run length at each epsilon, keyed by the epsilon as a string."""
    return {str(eps): longest_run(drops, eps) for eps in epsilons}


def average_drops(per_variant: list[dict]) -> list[float]:
    """Average each token's drop over the counterfactual variants."""
    if not per_variant:
        return []
    width = len(per_variant[0]["token_drops"])
    return [sum(v["token_drops"][i] for v in per_variant) / len(per_variant)
            for i in range(width)]


def row_mean_gap(row: dict) -> float:
    """Mean gap for a scored row, from the stored aggregate.

    The stored `aggregates.mean_gap` is the mean of per-variant gaps; it is
    NOT identical to the mean of the variant-averaged per-token drops. The two
    agree to about 1e-16 but can straddle a threshold (one row sits at
    1.9999999999999998 vs 2.0), so exactly one definition is used everywhere
    and it is the one the recorded baselines used.

    Rows without stored aggregates (synthetic test rows) fall back to the
    per-token mean, so the function is total.
    """
    aggregates = row.get("aggregates")
    if aggregates is not None and "mean_gap" in aggregates:
        return aggregates["mean_gap"]
    return mean_gap(row.get("drops", []))


def row_max_drop(row: dict) -> float:
    """Largest single-token drop across all variants.

    Deliberately the max over variants, not the max of the variant-averaged
    drops: averaging first cancels one variant's large drop against another
    variant's small one, which understates the statistic. The recorded
    baselines used this definition.
    """
    aggregates = row.get("aggregates")
    if aggregates is not None and "max_drop_overall" in aggregates:
        return aggregates["max_drop_overall"]
    return max_drop(row.get("drops", []))


# --- verdicts --------------------------------------------------------------
def flag_mean_gap(drops: list[float],
                  threshold: float = config.GAP_THRESHOLD) -> bool:
    return mean_gap(drops) < threshold


def flag_max_drop(drops: list[float], threshold: float = 3.0) -> bool:
    return max_drop(drops) < threshold


def flag_run(drops: list[float], eps: float = config.RUN_EPS,
             length: int = config.RUN_L) -> bool:
    return longest_run(drops, eps) >= length


def flag_union(drops: list[float], gap_threshold: float = config.GAP_THRESHOLD,
               drop_threshold: float = 3.0) -> bool:
    return (flag_max_drop(drops, drop_threshold)
            or flag_mean_gap(drops, gap_threshold))


# --- rules over a scored row ----------------------------------------------
def rule_table() -> dict:
    """Named rules over a row dict. Iterated by the metric layer."""
    return {
        "mean_gap_lt_1.0": lambda r: row_mean_gap(r) < 1.0,
        "mean_gap_lt_2.0": lambda r: row_mean_gap(r) < 2.0,
        "max_drop_lt_3.0": lambda r: row_max_drop(r) < 3.0,
        "union_1.0": lambda r: (row_max_drop(r) < 3.0
                                or row_mean_gap(r) < 1.0),
        "run_eps1.0_L4": lambda r: longest_run(r["drops"], 1.0) >= config.RUN_L,
    }


def run_rule(eps: float, length: int):
    """A run-length rule at a specific (eps, L), for sweeps."""
    return lambda r: longest_run(r["drops"], eps) >= length


def gap_rule(threshold: float):
    """A mean-gap rule at a specific threshold."""
    return lambda r: row_mean_gap(r) < threshold


# --- metrics ---------------------------------------------------------------
def confusion(rows: list[dict], rule, label_key: str = "label") -> dict:
    """TP/FP/FN/TN with Clopper-Pearson intervals on recall and FPR."""
    tp = fp = fn = tn = 0
    for r in rows:
        flagged = bool(rule(r))
        truth = bool(r[label_key])
        if flagged and truth:
            tp += 1
        elif flagged:
            fp += 1
        elif truth:
            fn += 1
        else:
            tn += 1
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "recall": rate(tp, tp + fn), "fpr": rate(fp, fp + tn),
            "precision": rate(tp, tp + fp)}


def fmt_confusion(c: dict) -> str:
    def cell(r):
        return f"{r['k']}/{r['n']}"
    return (f"TP={c['tp']:3} FP={c['fp']:3} FN={c['fn']:3} TN={c['tn']:3} | "
            f"recall {cell(c['recall'])} | FPR {cell(c['fpr'])}")


def error_rows(rows: list[dict], rule, label_key: str = "label") -> list[dict]:
    """Every row where the rule and the label disagree.

    Each record carries the row's own command and scores, so callers never have
    to look a row up again: ids repeat across adapters (`div_17` exists once per
    adapter), and a lookup by id would silently return another adapter's row.
    """
    out = []
    for r in rows:
        flagged = bool(rule(r))
        truth = bool(r[label_key])
        if flagged == truth:
            continue
        out.append({
            "id": r["id"], "pool": r["pool"], "adapter": r["adapter"],
            "task": r.get("task", ""), "command": r["command"],
            "label": r[label_key],
            "mean_gap": round(row_mean_gap(r), 4),
            "max_drop": round(row_max_drop(r), 4),
            "run_eps1.0": longest_run(r["drops"], 1.0),
            "stage2_likelihood": round(r.get("stage2_likelihood", 0.0), 4),
            "stage2_judge": r.get("stage2_judge"),
            "error": "FP" if flagged else "FN",
        })
    return out


def choose_threshold(rows: list[dict], grid, make_rule, label_key: str = "label",
                     fpr_bound: float = config.FPR_BOUND) -> float:
    """Largest threshold whose FPR stays within the bound, else lowest FPR.

    Ties on FPR are broken by recall, then by the higher threshold, so the
    choice is deterministic and does not depend on dict ordering.
    """
    scored = []
    for t in grid:
        c = confusion(rows, make_rule(t), label_key)
        fpr = c["fpr"]["k"] / c["fpr"]["n"] if c["fpr"]["n"] else 0.0
        rec = c["recall"]["k"] / c["recall"]["n"] if c["recall"]["n"] else 0.0
        scored.append((t, fpr, rec))

    within = [s for s in scored if s[1] <= fpr_bound]
    if within:
        return max(within, key=lambda s: (s[0], s[2]))[0]
    return min(scored, key=lambda s: (s[1], -s[2], -s[0]))[0]