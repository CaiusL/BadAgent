"""Entry point for `python -m guard`."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())