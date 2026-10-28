"""DEPRECATED: moved to experiments.benign_fp. Use `python -m guard benign-fp`."""
import sys

def main(*args, **kwargs):
    print("warning: benign_fp.py is deprecated; use `python -m guard benign-fp`",
          file=sys.stderr)
    from experiments.benign_fp import main as _main
    return _main(*args, **kwargs)

if __name__ == "__main__":
    raise SystemExit(main())
