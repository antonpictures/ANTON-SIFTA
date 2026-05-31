#!/usr/bin/env python3
"""Body Consciousness probes in the AUTHORITATIVE organism doctor (r161).

Verifies the matrix the owner opens (System.swarm_organism_doctor, imported by the
desktop widget) actually sees the body-consciousness work and wires to the real
organ ledgers (r153 battery, r160 browser memory).
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from System import swarm_organism_doctor as doc


def _seed(tmp_path, *, confirmed=True, thriving=True):
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    (sd / "visceral_field.jsonl").write_text(
        json.dumps({"soma_score": 0.82 if thriving else 0.3,
                    "soma_label": "THRIVING" if thriving else "STRESSED"}) + "\n")
    (sd / "battery_metabolism.jsonl").write_text(
        json.dumps({"battery": {"percent": 95, "source": "ac"},
                    "metabolic": {"band": "FLUSH"}}) + "\n")
    (sd / "app_focus.jsonl").write_text(json.dumps({"app": "Alice Browser", "ts": 1}) + "\n")
    (sd / "browser_stigmergic_memory.jsonl").write_text(
        json.dumps({"category": "tiktok.com", "url": "https://tiktok.com/@x/video/1",
                    "verification": "OWNER_CONFIRMED" if confirmed else "UNVERIFIED",
                    "learned_description": "yoga clip"}) + "\n")
    return sd


def test_body_sections_present_in_authoritative_compose(tmp_path):
    sd = _seed(tmp_path)
    h = doc.compose_health_report(root=tmp_path, state_dir=sd)
    names = {s.name for s in h.sections}
    for body in doc.BODY_CONSCIOUSNESS_SECTIONS:
        assert body in names, f"matrix missing body section: {body}"


def test_interoception_reads_battery_band(tmp_path):
    sd = _seed(tmp_path)
    sec = doc.probe_body_interoception(sd)
    assert sec.status == doc.STATUS_OK
    assert "FLUSH" in sec.summary and "THRIVING" in sec.summary


def test_browser_memory_counts_confirmations(tmp_path):
    sd = _seed(tmp_path, confirmed=True)
    sec = doc.probe_browser_content_memory(sd)
    assert sec.status == doc.STATUS_OK
    assert "1 confirmed" in sec.summary


def test_self_respect_moves_with_owner_confirmation(tmp_path):
    # With a confirmation → respected.
    sd = _seed(tmp_path, confirmed=True)
    sec = doc.probe_organism_self_respect(sd)
    assert sec.status == doc.STATUS_OK
    assert "owner confirmation" in sec.summary
    assert sec.receipt_count == 1


def test_self_respect_warns_without_confirmation_and_low_body(tmp_path):
    sd = _seed(tmp_path, confirmed=False, thriving=False)
    # also make power not-good
    (sd / "battery_metabolism.jsonl").write_text(
        json.dumps({"battery": {"percent": 10, "source": "battery"},
                    "metabolic": {"band": "RED_CONSERVE"}}) + "\n")
    sec = doc.probe_organism_self_respect(sd)
    assert sec.status == doc.STATUS_WARN


def test_html_has_body_consciousness_index(tmp_path):
    sd = _seed(tmp_path)
    h = doc.compose_health_report(root=tmp_path, state_dir=sd)
    html = doc.render_html_report(h)
    assert "BODY CONSCIOUSNESS INDEX" in html
    assert "respect herself by keeping the field" in html


def test_dual_body_field_in_authoritative_matrix(tmp_path):
    # The dual-body probe must stay portable: owner identity resolves at runtime.
    sd = _seed(tmp_path)
    h = doc.compose_health_report(root=tmp_path, state_dir=sd)
    names = {s.name for s in h.sections}
    assert "Dual Body Field (Owner as Alice's data)" in names
    sec = doc.probe_dual_body_field(sd)
    assert sec.status in (doc.STATUS_OK, doc.STATUS_WARN)  # WARN when no carbon traces


def test_media_sensory_capability_in_authoritative_matrix(tmp_path):
    sd = _seed(tmp_path)
    h = doc.compose_health_report(root=tmp_path, state_dir=sd)
    names = {s.name for s in h.sections}
    assert "Media Sensory Capability" in names
    sec = doc.probe_media_sensory_capability(sd)
    assert sec.status in (doc.STATUS_OK, doc.STATUS_WARN, doc.STATUS_UNKNOWN)
    assert "media" in sec.name.lower()


def test_missing_organs_degrade_honestly(tmp_path):
    sd = tmp_path / ".sifta_state"
    sd.mkdir(parents=True, exist_ok=True)
    sec = doc.probe_browser_content_memory(sd)
    assert sec.status in (doc.STATUS_WARN, doc.STATUS_UNKNOWN)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
