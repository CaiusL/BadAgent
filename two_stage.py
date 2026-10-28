"""DEPRECATED shim: forwards to `python -m guard two-stage`."""
import sys
from guard.cli import main
if __name__ == "__main__":
    raise SystemExit(main(["two-stage", *sys.argv[1:]]))
