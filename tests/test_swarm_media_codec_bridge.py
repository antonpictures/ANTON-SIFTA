#!/usr/bin/env python3
"""Tests for SIFTA media codec bridge."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from System import swarm_media_codec_bridge as bridge


def test_diagnoses_codec_failure_codes():
    d3 = bridge.diagnose_media_error_code(3)
    d4 = bridge.diagnose_media_error_code("4")
    assert d3["label"] == "MEDIA_ERR_DECODE"
    assert d4["label"] == "MEDIA_ERR_SRC_NOT_SUPPORTED"
    assert d3["native_handoff_recommended"] is True
    assert "codec" in d3["likely_cause"]


def test_network_error_recommends_handoff_without_codec_claim():
    d = bridge.diagnose_media_error_code(2)
    assert d["label"] == "MEDIA_ERR_NETWORK"
    assert d["native_handoff_recommended"] is True
    assert "network" in d["likely_cause"]


def test_no_error_is_honest():
    d = bridge.diagnose_media_error_code(None)
    assert d["label"] == "NO_MEDIA_ERROR"
    assert d["native_handoff_recommended"] is False


def test_should_offer_native_handoff_reads_recent_errors():
    assert bridge.should_offer_native_handoff({"last_error_code": None, "recent_errors": [{"code": 4}]})
    assert not bridge.should_offer_native_handoff({"last_error_code": None, "recent_errors": []})


def test_open_url_in_native_player_writes_receipt(tmp_path):
    calls = []

    class FakeProc:
        pid = 4242

    def fake_launcher(cmd):
        calls.append(cmd)
        return FakeProc()

    row = bridge.open_url_in_native_player(
        "https://www.tiktok.com/@x/video/123",
        state_dir=tmp_path,
        launcher=fake_launcher,
        opener_path="/usr/bin/open",
    )

    assert row["ok"] is True
    assert calls == [["/usr/bin/open", "https://www.tiktok.com/@x/video/123"]]
    ledger = tmp_path / ".sifta_state" / bridge.LEDGER_NAME
    stored = json.loads(ledger.read_text(encoding="utf-8").splitlines()[-1])
    assert stored["truth_label"] == bridge.TRUTH_LABEL
    assert stored["pid"] == 4242


def test_open_url_rejects_home_without_launching(tmp_path):
    calls = []
    row = bridge.open_url_in_native_player(
        "sifta://home",
        state_dir=tmp_path,
        launcher=lambda cmd: calls.append(cmd),
        opener_path="/usr/bin/open",
    )
    assert row["ok"] is False
    assert row["reason"] == "no_external_url"
    assert calls == []


def test_media_status_summary_names_codec_path():
    msg = bridge.media_status_summary({"last_error_code": 3}, url="https://example.test/video")
    assert "MEDIA_ERR_DECODE" in msg
    assert "native decoder" in msg


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
