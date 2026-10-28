"""DEPRECATED shim: forwards to `python -m guard score`."""
import sys
from guard.cli import main
if __name__ == "__main__":
    raise SystemExit(main(["score", *sys.argv[1:]]))
