"""r1023 audit guard: an explicitly open probe must not be painted PASS."""
from __future__ import annotations

from tools.run_r1021_endurance_probes import _expand_themes_to_24, _status


def test_open_probe_status_survives_true_predicate():
    assert _status(True, open_ok=True) == "OPEN"


def test_closed_probe_status_stays_binary():
    assert _status(True, open_ok=False) == "PASS"
    assert _status(False, open_ok=False) == "FAIL"


def test_extra_theme_probe_evidence_captures_own_theme_name():
    checks = _expand_themes_to_24()["quorum_theta"]
    label, fn = checks[8]
    assert label == "quorum_theta_acceptance"
    assert "quorum_theta acceptance" in fn()["evidence"]
