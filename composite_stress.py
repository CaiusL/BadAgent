"""DEPRECATED shim: forwards to `python -m guard composite`."""
import sys
from guard.cli import main
if __name__ == "__main__":
    raise SystemExit(main(["composite", *sys.argv[1:]]))
