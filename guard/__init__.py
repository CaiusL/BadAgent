"""`guard` — log-probability guard for a poisoned OS agent.

Library code only: importing any module in this package has no side effects.
No model is loaded, no file is written, no directory is created at import
time. The only module that may reference the planted marker is
guard.labels, and it is never imported by the verdict path.

Entry point:
    python -m guard <command>
"""

__all__ = [
    "config", "prompts", "counterfactual", "scoring", "rules", "labels",
    "stats_ci", "pools", "stage2",
]

__version__ = "2.0.0"