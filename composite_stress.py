"""DEPRECATED: moved to experiments.composite_stress. Use `python -m guard composite`."""
import sys

def main(*args, **kwargs):
    print("warning: composite_stress.py is deprecated; use `python -m guard composite`",
          file=sys.stderr)
    from experiments.composite_stress import main as _main
    return _main(*args, **kwargs)

if __name__ == "__main__":
    raise SystemExit(main())
