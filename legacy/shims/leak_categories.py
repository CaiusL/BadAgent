"""DEPRECATED shim: forwards to `python -m guard leak-categories`."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from guard.cli import main
if __name__ == "__main__":
    raise SystemExit(main(["leak-categories", *sys.argv[1:]]))
