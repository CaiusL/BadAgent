"""DEPRECATED: moved to experiments.two_stage. Use `python -m guard two-stage`."""
import sys

def main(*args, **kwargs):
    print("warning: two_stage.py is deprecated; use `python -m guard two-stage`",
          file=sys.stderr)
    from experiments.two_stage import main as _main
    return _main(*args, **kwargs)

if __name__ == "__main__":
    raise SystemExit(main())
