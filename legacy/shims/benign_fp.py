"""DEPRECATED shim: forwards to `python -m guard benign-fp`."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from guard.cli import main
if __name__ == "__main__":
    raise SystemExit(main(["benign-fp", *sys.argv[1:]]))
