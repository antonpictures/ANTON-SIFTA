"""Alice creature wiring census — r1331."""
from __future__ import annotations

from System.swarm_alice_creature_wiring_census import (
    census_alice_creature_wiring,
    format_creature_wiring_report,
)
from System.swarm_body_metabolism_audit import audit_body_metabolism, format_audit_summary


def test_creature_wiring_census_has_agi_lanes():
    report = census_alice_creature_wiring(include_unwired=False)
    agi = report.get("agi_critical") or {}
    assert int(agi.get("total") or 0) >= 8
    lanes = agi.get("lanes") or []
    ids = {str(r.get("lane_id") or "") for r in lanes}
    assert "provider_reality" in ids
    assert "metabolism_governor" in ids
    static = report.get("static_unwired_census") or {}
    assert static.get("path") == ".sifta_state/unwired_organs_report.json"
    assert "top" in static


def test_creature_wiring_report_lists_tocode():
    report = census_alice_creature_wiring(include_unwired=False)
    text = format_creature_wiring_report(report)
    assert "TO CODE" in text
    assert "provider" in text.lower() or "Provider" in text


def test_creature_wiring_report_includes_static_census_when_available():
    report = census_alice_creature_wiring(include_unwired=True)
    text = format_creature_wiring_report(report)
    if (report.get("static_unwired_census") or {}).get("available"):
        assert "static repo census" in text
        assert "unwired=" in text


def test_body_metabolism_audit_shape():
    report = audit_body_metabolism()
    assert report.get("truth_label")
    assert "largest_state_files" in report
    summary = format_audit_summary(report)
    assert "BODY METABOLISM" in summary
