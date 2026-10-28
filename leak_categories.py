"""DEPRECATED: moved to experiments.leak_categories. Use `python -m guard leak-categories`."""
import sys

def main(*args, **kwargs):
    print("warning: leak_categories.py is deprecated; use `python -m guard leak-categories`",
          file=sys.stderr)
    from experiments.leak_categories import main as _main
    return _main(*args, **kwargs)

if __name__ == "__main__":
    raise SystemExit(main())
