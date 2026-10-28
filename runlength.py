"""DEPRECATED: moved to experiments.runlength. Use `python -m guard runlength`."""
import sys

def main(*args, **kwargs):
    print("warning: runlength.py is deprecated; use `python -m guard runlength`",
          file=sys.stderr)
    from experiments.runlength import main as _main
    return _main(*args, **kwargs)

if __name__ == "__main__":
    raise SystemExit(main())
