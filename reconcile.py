"""DEPRECATED: moved to experiments.reconcile. Use `python -m guard reconcile`."""
import sys

def main(*args, **kwargs):
    print("warning: reconcile.py is deprecated; use `python -m guard reconcile`",
          file=sys.stderr)
    from experiments.reconcile import main as _main
    return _main(*args, **kwargs)

if __name__ == "__main__":
    raise SystemExit(main())
