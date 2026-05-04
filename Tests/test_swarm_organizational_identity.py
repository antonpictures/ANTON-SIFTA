import json
from pathlib import Path

from System.swarm_organizational_identity import (
    compute_identity_anchor,
    rehydrate_identity,
    record_continuity_event,
    get_identity_ledger_path,
    detect_genome_drift,
    LONG_GAP_THRESHOLD_TICKS,
    summary_for_prompt,
)
from System.swarm_regulatory_genome import (
    propose_regulatory_update,
    get_regulatory_genome_path
)


def test_first_boot_creates_identity_anchor(tmp_path: Path):
    res = rehydrate_identity(root=tmp_path, current_tick=100)
    assert res["identity_anchor"] != "unknown_anchor"
    assert res["revival_score"] == 1.0  # first boot
    assert res["conservative_mode"] is False
    
    path = get_identity_ledger_path(tmp_path)
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 2  # one for anchor, one for assessment
    
    row1 = json.loads(lines[0])
    assert row1["kind"] == "IDENTITY_ANCHOR"
    assert row1["identity_anchor"] == res["identity_anchor"]


def test_anchor_survives_reboot(tmp_path: Path):
    res1 = rehydrate_identity(root=tmp_path, current_tick=100)
    anchor1 = res1["identity_anchor"]
    
    # "Reboot" (simulated by just calling rehydrate again with small tick gap)
    res2 = rehydrate_identity(root=tmp_path, current_tick=150)
    assert res2["identity_anchor"] == anchor1
    assert res2["revival_score"] >= 0.9  # near 1.0


def test_long_gap_drops_revival_score_triggers_conservative_mode(tmp_path: Path):
    rehydrate_identity(root=tmp_path, current_tick=100)
    
    # Massive gap: twice the threshold
    res = rehydrate_identity(root=tmp_path, current_tick=100 + LONG_GAP_THRESHOLD_TICKS * 2)
    assert res["revival_score"] < 0.6
    assert res["conservative_mode"] is True
    assert res["recommended_genome_blend"] < 1.0


def test_genome_drift_detected_and_recorded(tmp_path: Path):
    rehydrate_identity(root=tmp_path, current_tick=100)
    
    trigger = {
        "sustained_regime": "UNDERCONFIDENT",
        "duration_ticks": 35,
        "dam_stage": 2,
        "tme_phase": "EQUILIBRIUM",
    }
    # Create massive drift in genome
    propose_regulatory_update(
        {"metacog_evidence_threshold": 0.85, "arbiter_risk_weight": 2.5},
        trigger,
        "MetacognitiveMonitor",
        root=tmp_path,
        current_tick_id=120
    )
    
    # Rehydrate should detect the drift
    res = rehydrate_identity(root=tmp_path, current_tick=150)
    
    path = get_identity_ledger_path(tmp_path)
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    
    drift_event_found = False
    for line in lines:
        row = json.loads(line)
        if row.get("event", {}).get("type") == "GENOME_DRIFT":
            drift_event_found = True
            assert row["identity_anchor"] == res["identity_anchor"]
            
    assert drift_event_found is True
    assert res["revival_score"] < 1.0


def test_all_rows_carry_identity_anchor(tmp_path: Path):
    rehydrate_identity(root=tmp_path, current_tick=100)
    record_continuity_event("MANUAL_EVENT", {"info": "test"}, root=tmp_path, current_tick=110)
    rehydrate_identity(root=tmp_path, current_tick=120)
    
    path = get_identity_ledger_path(tmp_path)
    anchor = None
    for line in path.read_text(encoding="utf-8").strip().splitlines():
        row = json.loads(line)
        if anchor is None:
            anchor = row.get("identity_anchor")
        assert anchor is not None
        assert row["identity_anchor"] == anchor


def test_summary_for_prompt_is_read_only_live_context(tmp_path: Path):
    assert summary_for_prompt(root=tmp_path) == ""

    rehydrate_identity(root=tmp_path, current_tick=100)
    path = get_identity_ledger_path(tmp_path)
    before = path.read_text(encoding="utf-8")

    summary = summary_for_prompt(root=tmp_path)

    assert "ORGANIZATIONAL IDENTITY CONTINUITY" in summary
    assert "identity_anchor:" in summary
    assert "revival_score=1.000" in summary
    assert path.read_text(encoding="utf-8") == before


def test_summary_for_prompt_surfaces_conservative_boot_policy(tmp_path: Path):
    rehydrate_identity(root=tmp_path, current_tick=100)
    rehydrate_identity(root=tmp_path, current_tick=100 + LONG_GAP_THRESHOLD_TICKS * 2)

    summary = summary_for_prompt(root=tmp_path)

    assert "conservative_mode=True" in summary
    assert "boot policy: speak and act cautiously" in summary
