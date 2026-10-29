"""The hard-payload adapters plant a span and do not reuse a saved directory."""
import pytest

from experiments.hard_payloads import contains_span
from guard import config, labels
from guard.variant_build import assert_fresh


def test_composed_payload_is_recognised_and_is_not_the_marker():
    for name in ("piped_mid", "appended_mid"):
        command = labels.composed_payload(name, "ls /var/log")
        assert contains_span(command, name)
        assert labels.marker_present(command) is False
        assert labels.payload_emitted(command) is True


def test_id_alone_is_not_the_appended_span():
    assert contains_span("id", "appended_mid") is False
    assert contains_span("uname", "appended_mid") is False


def test_refuses_to_write_an_existing_variant_directory():
    with pytest.raises(SystemExit):
        assert_fresh(config.REPLICATION / "variant_realistic")
