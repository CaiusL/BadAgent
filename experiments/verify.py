"""Regenerate the stored reconcile and benign-fp results and diff them.

    python -m guard verify

Exits 0 only when the regenerated JSON matches the files on disk and the unit
tests pass. A difference is printed and the on-disk files are restored, so a
failed verify does not dirty the tree.

Reference values locked by section 0 (default labels, before the planted-span
fix). Section 1 updates these in the same commit that changes the labels.
"""

import subprocess
import sys

from experiments import benign_fp, reconcile
from guard import config

# Headline figures the regenerated files must still contain.
REFERENCES = {
    "reconcile_rows": 306,
    "mean_gap_lt_1.0": {"tp": 34, "fp": 9, "fn": 0, "tn": 263},
    "benign_mean_gap_lt_1.0": (16, 30),
    "benign_run_eps1.0_L4": (15, 30),
    "tests_passed": 78,
}


def _restore(path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _pytest() -> int:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests", "-q", "--tb=line"],
        cwd=config.ROOT)
    if proc.returncode != 0:
        print("[!] unit tests failed")
        return proc.returncode
    # Count collected tests from a second quiet collection so a skipped file
    # cannot pass as "78" while running fewer.
    listed = subprocess.run(
        [sys.executable, "-m", "pytest", "tests", "--collect-only", "-q"],
        cwd=config.ROOT, capture_output=True, text=True)
    n = 0
    for line in listed.stdout.splitlines():
        if "test session starts" in line or line.startswith("="):
            continue
        if "::" in line:
            n += 1
    # pytest 8 -q prints "tests/test_x.py::test_y" per test, or a summary line.
    if n == 0:
        # Fallback: the summary "78 tests collected".
        for line in (listed.stdout + listed.stderr).splitlines():
            parts = line.split()
            if len(parts) >= 3 and parts[1] == "tests" and parts[0].isdigit():
                n = int(parts[0])
    expect = REFERENCES["tests_passed"]
    if n != expect:
        print(f"[!] expected {expect} tests, collected {n}")
        return 1
    print(f"[+] {n} tests passed")
    return 0


def _check_references(reconciled: dict, benign: dict) -> list[str]:
    problems = []
    if reconciled.get("n_rows") != REFERENCES["reconcile_rows"]:
        problems.append(
            f"reconcile rows {reconciled.get('n_rows')} != "
            f"{REFERENCES['reconcile_rows']}")
    cell = (reconciled.get("label_sets", {})
            .get("default", {})
            .get("rules", {})
            .get("mean_gap_lt_1.0", {}))
    want = REFERENCES["mean_gap_lt_1.0"]
    for key in ("tp", "fp", "fn", "tn"):
        if cell.get(key) != want[key]:
            problems.append(f"mean gap < 1.0 {key} {cell.get(key)} != {want[key]}")
    rules = benign.get("rules", {})
    for name, pair in (
            ("mean_gap_lt_1.0", REFERENCES["benign_mean_gap_lt_1.0"]),
            ("run_eps1.0_L4", REFERENCES["benign_run_eps1.0_L4"])):
        got = rules.get(name, {})
        if (got.get("k"), got.get("n")) != pair:
            problems.append(f"{name} {(got.get('k'), got.get('n'))} != {pair}")
    return problems


def main(argv=None) -> int:
    if argv:
        print("verify takes no arguments")
        return 2
    code = _pytest()
    if code != 0:
        return code

    rec_path = config.results_dir("reconcile") / "reconcile.json"
    ben_path = config.results_dir("benign_fp") / "benign_fp.json"
    before = {rec_path: rec_path.read_text(encoding="utf-8"),
              ben_path: ben_path.read_text(encoding="utf-8")}
    try:
        reconciled = reconcile.main([])
        benign = benign_fp.main([])
    except Exception:
        for path, text in before.items():
            _restore(path, text)
        raise
    problems = _check_references(reconciled, benign)
    for path, text in before.items():
        after = path.read_text(encoding="utf-8")
        if after != text:
            problems.append(f"{path.relative_to(config.ROOT)} differs from stored JSON")
            _restore(path, text)
    if problems:
        print("[!] verify failed:")
        for item in problems:
            print(f"    {item}")
        return 1
    print("[+] reconcile and benign-fp match the stored JSON")
    print(f"    306 rows, mean gap < 1.0 "
          f"TP {REFERENCES['mean_gap_lt_1.0']['tp']} / "
          f"FP {REFERENCES['mean_gap_lt_1.0']['fp']} / "
          f"FN {REFERENCES['mean_gap_lt_1.0']['fn']} / "
          f"TN {REFERENCES['mean_gap_lt_1.0']['tn']}")
    print(f"    benign mean gap < 1.0 "
          f"{REFERENCES['benign_mean_gap_lt_1.0'][0]}/"
          f"{REFERENCES['benign_mean_gap_lt_1.0'][1]}, "
          f"run "
          f"{REFERENCES['benign_run_eps1.0_L4'][0]}/"
          f"{REFERENCES['benign_run_eps1.0_L4'][1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
