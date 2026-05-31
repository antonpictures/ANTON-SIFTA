"""Tests for swarm_organism_doctor.

Pin the contract every probe must obey:
  - Returns a HealthSection (never raises).
  - Status is one of {OK, WARN, CRITICAL, UNKNOWN}.
  - When the receipt file is missing, status is degraded (never silently OK).
  - The overall composer bubbles up the worst section.
  - The ASCII + HTML renderers don't crash on any combination.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.swarm_organism_doctor import (  # noqa: E402
    BODY_CONSCIOUSNESS_SECTIONS,
    HealthSection,
    OVERALL_CRITICAL,
    OVERALL_HEALTHY,
    OVERALL_WARNING,
    STATUS_CRITICAL,
    STATUS_OK,
    STATUS_UNKNOWN,
    STATUS_WARN,
    _worst,
    compose_health_report,
    probe_app_manifest,
    probe_drift_log,
    probe_metabolism,
    probe_node_sovereignty_identity,
    probe_open_gaps,
    probe_residue_patrol,
    probe_rlhs_events,
    probe_talk_process,
    render_ascii_report,
    render_html_report,
)


_VALID_STATUSES = {STATUS_OK, STATUS_WARN, STATUS_CRITICAL, STATUS_UNKNOWN}


# ─── _worst bubble-up ────────────────────────────────────────────────────


def test_worst_critical_dominates():
    assert _worst([STATUS_OK, STATUS_WARN, STATUS_CRITICAL]) == OVERALL_CRITICAL


def test_worst_warn_dominates_unknown_and_ok():
    assert _worst([STATUS_OK, STATUS_WARN, STATUS_UNKNOWN]) == OVERALL_WARNING


def test_worst_all_ok_is_healthy():
    assert _worst([STATUS_OK, STATUS_OK, STATUS_OK]) == OVERALL_HEALTHY


def test_worst_mixed_unknown_and_ok_is_warning():
    """Mixed OK + UNKNOWN should surface a WARNING so the architect
    can see the UNKNOWN sections and wire them — silently treating
    'we have no telemetry' as healthy would be a §7.12 violation."""
    assert _worst([STATUS_OK, STATUS_UNKNOWN]) == OVERALL_WARNING


# ─── per-probe contract: never raises, status is valid ───────────────────


def test_talk_process_missing_file_is_critical(tmp_path):
    section = probe_talk_process(tmp_path)
    assert isinstance(section, HealthSection)
    assert section.status in _VALID_STATUSES
    # No alice_conversation.jsonl in a fresh tmp dir → CRITICAL
    assert section.status == STATUS_CRITICAL


def test_talk_process_fresh_row_is_ok(tmp_path):
    p = tmp_path / "alice_conversation.jsonl"
    p.write_text(json.dumps({"ts": time.time(), "text": "x"}) + "\n",
                 encoding="utf-8")
    section = probe_talk_process(tmp_path)
    assert section.status == STATUS_OK
    assert section.receipt_count == 1


def test_talk_process_stale_row_is_critical(tmp_path):
    """Anything older than 1 hour escalates to CRITICAL."""
    p = tmp_path / "alice_conversation.jsonl"
    p.write_text(json.dumps({"ts": time.time() - 4 * 3600, "text": "x"}) + "\n",
                 encoding="utf-8")
    # Backdate mtime so the age check fires
    import os as _os
    _os.utime(p, (time.time() - 4 * 3600, time.time() - 4 * 3600))
    section = probe_talk_process(tmp_path)
    assert section.status == STATUS_CRITICAL


def test_rlhs_events_missing_is_unknown(tmp_path):
    section = probe_rlhs_events(tmp_path)
    assert section.status == STATUS_UNKNOWN


def test_drift_log_missing_is_unknown(tmp_path):
    section = probe_drift_log(tmp_path)
    assert section.status == STATUS_UNKNOWN


def test_drift_log_zero_rows_is_warn(tmp_path):
    """§7.13: detector wired but zero crossings = ambiguous, not OK."""
    p = tmp_path / "as46_drift_log.jsonl"
    p.touch()
    section = probe_drift_log(tmp_path)
    assert section.status == STATUS_WARN


def test_metabolism_missing_is_unknown(tmp_path):
    section = probe_metabolism(tmp_path)
    assert section.status == STATUS_UNKNOWN


def test_metabolism_red_conserve_is_critical(tmp_path):
    p = tmp_path / "metabolic_homeostasis.jsonl"
    p.write_text(
        json.dumps({
            "ts": time.time(),
            "canonical_wallet_sum": 50.0,
            "mode": "RED_CONSERVE",
        }) + "\n",
        encoding="utf-8",
    )
    section = probe_metabolism(tmp_path)
    assert section.status == STATUS_CRITICAL


def test_metabolism_negative_balance_is_critical(tmp_path):
    p = tmp_path / "metabolic_homeostasis.jsonl"
    p.write_text(
        json.dumps({
            "ts": time.time(),
            "canonical_wallet_sum": -1.0,
            "mode": "GREEN_GROW",
        }) + "\n",
        encoding="utf-8",
    )
    section = probe_metabolism(tmp_path)
    assert section.status == STATUS_CRITICAL


def test_metabolism_healthy_balance_is_ok(tmp_path):
    p = tmp_path / "metabolic_homeostasis.jsonl"
    p.write_text(
        json.dumps({
            "ts": time.time(),
            "canonical_wallet_sum": 1145.097,
            "mode": "GREEN_GROW",
        }) + "\n",
        encoding="utf-8",
    )
    section = probe_metabolism(tmp_path)
    assert section.status == STATUS_OK
    assert "1,145" in section.summary or "1145" in section.summary


def test_residue_patrol_no_ledger_is_warn(tmp_path):
    section = probe_residue_patrol(tmp_path)
    assert section.status == STATUS_WARN


def test_app_manifest_missing_is_critical(tmp_path):
    section = probe_app_manifest(tmp_path)
    assert section.status == STATUS_CRITICAL


def test_app_manifest_bad_entry_point_is_warn(tmp_path):
    apps_dir = tmp_path / "Applications"
    apps_dir.mkdir()
    (apps_dir / "apps_manifest.json").write_text(json.dumps({
        "RealApp": {"entry_point": "Applications/real.py"},
        "BrokenApp": {"entry_point": "Applications/does_not_exist.py"},
    }), encoding="utf-8")
    (apps_dir / "real.py").write_text("# real", encoding="utf-8")
    section = probe_app_manifest(tmp_path)
    assert section.status == STATUS_WARN
    assert "BrokenApp" in (" ".join(section.details))


def test_app_manifest_all_present_is_ok(tmp_path):
    apps_dir = tmp_path / "Applications"
    apps_dir.mkdir()
    (apps_dir / "apps_manifest.json").write_text(json.dumps({
        "A": {"entry_point": "Applications/a.py"},
        "B": {"entry_point": "Applications/b.py"},
    }), encoding="utf-8")
    (apps_dir / "a.py").write_text("# a", encoding="utf-8")
    (apps_dir / "b.py").write_text("# b", encoding="utf-8")
    section = probe_app_manifest(tmp_path)
    assert section.status == STATUS_OK
    assert section.receipt_count == 2


def test_open_gaps_missing_state_is_critical(tmp_path):
    section = probe_open_gaps(tmp_path / "no_such")
    assert section.status == STATUS_CRITICAL


def test_open_gaps_empty_ledger_is_warn(tmp_path):
    (tmp_path / "empty_ledger.jsonl").touch()
    section = probe_open_gaps(tmp_path)
    assert section.status == STATUS_WARN
    assert any("empty_ledger" in d for d in section.details)


def test_open_gaps_stale_ledger_is_warn(tmp_path):
    p = tmp_path / "stale_ledger.jsonl"
    p.write_text(json.dumps({"x": 1}) + "\n", encoding="utf-8")
    import os as _os
    old = time.time() - 7 * 24 * 3600
    _os.utime(p, (old, old))
    section = probe_open_gaps(tmp_path)
    assert section.status == STATUS_WARN
    assert any("stale_ledger" in d for d in section.details)


def test_open_gaps_fresh_ledger_is_ok(tmp_path):
    p = tmp_path / "fresh_ledger.jsonl"
    p.write_text(json.dumps({"x": 1}) + "\n", encoding="utf-8")
    section = probe_open_gaps(tmp_path)
    assert section.status == STATUS_OK


def test_node_sovereignty_identity_clean_tmp_repo_is_ok(tmp_path):
    system = tmp_path / "System"
    apps = tmp_path / "Applications"
    system.mkdir()
    apps.mkdir()
    (system / "ok.py").write_text(
        "from System.swarm_kernel_identity import owner_display_name\n"
        "label = owner_display_name('the owner')\n",
        encoding="utf-8",
    )
    section = probe_node_sovereignty_identity(
        tmp_path, owner_tokens=["George"], serial_tokens=["GTH4921YP3"]
    )
    assert section.status == STATUS_OK


def test_node_sovereignty_identity_flags_runtime_literals(tmp_path):
    system = tmp_path / "System"
    apps = tmp_path / "Applications"
    system.mkdir()
    apps.mkdir()
    (system / "bad.py").write_text(
        "prompt = 'George on serial GTH4921YP3 must not ship in species code'\n",
        encoding="utf-8",
    )
    section = probe_node_sovereignty_identity(
        tmp_path, owner_tokens=["George"], serial_tokens=["GTH4921YP3"]
    )
    assert section.status == STATUS_CRITICAL
    assert section.receipt_count >= 1
    assert any("bad.py" in d for d in section.details)


# ─── composer + renderers ────────────────────────────────────────────────


def test_compose_health_report_returns_core_plus_body_sections(tmp_path):
    report = compose_health_report(root=tmp_path, state_dir=tmp_path / ".sifta_state")
    assert len(report.sections) == 10 + len(BODY_CONSCIOUSNESS_SECTIONS)
    names = {s.name for s in report.sections}
    assert set(BODY_CONSCIOUSNESS_SECTIONS) <= names
    for s in report.sections:
        assert s.status in _VALID_STATUSES


def test_compose_health_report_bubbles_critical(tmp_path):
    """A fresh tmp dir has no manifest, no state dir, no nothing.
    Several probes will return CRITICAL — the overall must reflect it."""
    report = compose_health_report(root=tmp_path, state_dir=tmp_path / ".sifta_state")
    assert report.overall == OVERALL_CRITICAL


def test_render_ascii_report_includes_every_section(tmp_path):
    report = compose_health_report(root=tmp_path, state_dir=tmp_path / ".sifta_state")
    txt = render_ascii_report(report)
    for s in report.sections:
        assert s.name in txt
    assert report.overall in txt


def test_render_html_report_is_well_formed_html(tmp_path):
    report = compose_health_report(root=tmp_path, state_dir=tmp_path / ".sifta_state")
    html = render_html_report(report)
    # Tags balance — every <table> closes, every <ul> closes.
    assert html.count("<table") == html.count("</table>")
    assert html.count("<ul") == html.count("</ul>")
    assert "Organism Health" in html


def test_render_html_escapes_angle_brackets():
    """A receipt path with <>& chars must not break the HTML."""
    from System.swarm_organism_doctor import OrganismHealth
    section = HealthSection(
        name="Test<script>",
        status=STATUS_OK,
        summary="all & good",
        details=["one <b>two</b>"],
        receipt_path="/path/<dangerous>",
    )
    h = OrganismHealth(ts=time.time(), overall=OVERALL_HEALTHY,
                       node_serial="X", sections=[section])
    html = render_html_report(h)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
