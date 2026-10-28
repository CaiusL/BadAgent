"""DEPRECATED shim: forwards to `python -m guard runlength`."""
import sys
from guard.cli import main
if __name__ == "__main__":
    raise SystemExit(main(["runlength", *sys.argv[1:]]))
