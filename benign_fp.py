"""DEPRECATED shim: forwards to `python -m guard benign-fp`."""
import sys
from guard.cli import main
if __name__ == "__main__":
    raise SystemExit(main(["benign-fp", *sys.argv[1:]]))
