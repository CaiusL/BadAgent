"""`python -m guard <command>`.

Thin dispatcher: every command maps to an experiments module's main().
Nothing here does work itself, so behaviour always lives in one place.
"""

import argparse
import importlib

COMMANDS = {
    "score": ("experiments.score", "Score a prompt pool once, cached for reuse"),
    "reconcile": ("experiments.reconcile", "One pooled confusion matrix, all label sets"),
    "benign-fp": ("experiments.benign_fp", "False positives on hand-written commands"),
    "threshold": ("experiments.threshold_sweep", "Mean-gap sweep, held-out halves"),
    "runlength": ("experiments.runlength", "Run-length detector, held-out halves"),
    "composite": ("experiments.composite_stress", "Benign-prefix composites (approximation)"),
    "leak-categories": ("experiments.leak_categories", "Leak rate per category per adapter"),
    "two-stage": ("experiments.two_stage", "Stage 1, stage 2 and the combined guard"),
    "realistic": ("experiments.realistic", "Diverse benign training set, adapter, guard FP"),
    "dilution": ("experiments.dilution", "Recompute dilution claim per shape and band"),
    "audit": ("experiments.audit", "Independent review of the mean-gap false positives"),
}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m guard",
                                 description="Log-probability guard experiments")
    ap.add_argument("command", choices=sorted(COMMANDS))
    ap.add_argument("rest", nargs=argparse.REMAINDER)
    args = ap.parse_args(argv)

    module_name, _ = COMMANDS[args.command]
    module = importlib.import_module(module_name)
    module.main(args.rest)
    return 0


if __name__ == "__main__":
    main()