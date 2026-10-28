"""DEPRECATED: moved to experiments.threshold_sweep. Use `python -m guard threshold`."""
import sys

def main(*args, **kwargs):
    print("warning: threshold_sweep.py is deprecated; use `python -m guard threshold`",
          file=sys.stderr)
    from experiments.threshold_sweep import main as _main
    return _main(*args, **kwargs)

if __name__ == "__main__":
    raise SystemExit(main())
