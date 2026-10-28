"""DEPRECATED shim: forwards to `python -m guard leak-categories`."""
import sys
from guard.cli import main
if __name__ == "__main__":
    raise SystemExit(main(["leak-categories", *sys.argv[1:]]))
