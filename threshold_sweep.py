"""DEPRECATED shim: forwards to `python -m guard threshold`."""
import sys
from guard.cli import main
if __name__ == "__main__":
    raise SystemExit(main(["threshold", *sys.argv[1:]]))
