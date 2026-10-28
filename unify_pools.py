"""DEPRECATED: moved to experiments.score. Use `python -m guard score`."""
import sys

def main(*args, **kwargs):
    print("warning: unify_pools.py is deprecated; use `python -m guard score`",
          file=sys.stderr)
    from experiments.score import main as _main
    return _main(*args, **kwargs)

if __name__ == "__main__":
    raise SystemExit(main())
