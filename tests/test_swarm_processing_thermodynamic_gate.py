import json

from System import swarm_processing_thermodynamic_gate as gate
from System.swarm_processing_thermodynamic_gate import (
    LEDGER_NAME,
    TRUTH_LABEL,
    prompt_context,
    request_processing_clearance,
)


def test_processing_gate_allows_when_body_has_headroom(tmp_path, monkeypatch):
    monkeypatch.setattr(
        gate,
        "_sample_body",
        lambda state: {
            "interoception": {
                "cpu_load_norm": 0.1,
                "allostatic_load_norm": 0.2,
                "thermal_pressure": "Normal",
            },
            "metabolic": {
                "mode": "GREEN_GROW",
                "pressure": 0.1,
                "budget_multiplier": 0.9,
                "must_rest": False,
                "rest_seconds": 0.0,
            },
            "thermal": {"thermal_warning_level": 0, "thermal_pressure": "Normal"},
            "energy": {"charge_pct": 80.0, "low_power_mode": False},
        },
    )

    row = request_processing_clearance(
        "ambient_whisper_transcription",
        expected_value=0.6,
        payload={"duration_s": 6.0, "model": "small"},
        state_dir=tmp_path,
    )

    assert row["truth_label"] == TRUTH_LABEL
    assert row["allowed"] is True
    assert row["action"] == "allow"
    assert row["receipt_hash"]
    assert (tmp_path / LEDGER_NAME).exists()


def test_processing_gate_defers_on_critical_thermal_body(tmp_path, monkeypatch):
    monkeypatch.setattr(
        gate,
        "_sample_body",
        lambda state: {
            "interoception": {
                "cpu_load_norm": 0.9,
                "allostatic_load_norm": 0.4,
                "thermal_pressure": "Critical",
            },
            "metabolic": {
                "mode": "GREEN_GROW",
                "pressure": 0.1,
                "budget_multiplier": 0.8,
                "must_rest": False,
                "rest_seconds": 0.0,
            },
            "thermal": {"thermal_warning_level": 3, "thermal_pressure": "Critical"},
            "energy": {"charge_pct": 80.0, "low_power_mode": False},
        },
    )

    row = request_processing_clearance(
        "ambient_whisper_transcription",
        expected_value=0.5,
        payload={"duration_s": 8.0, "model": "small"},
        state_dir=tmp_path,
    )

    assert row["allowed"] is False
    assert row["action"] == "defer"
    assert "thermal_critical" in row["reasons"]
    assert row["prev_hash"] == "GENESIS"
    saved = json.loads((tmp_path / LEDGER_NAME).read_text(encoding="utf-8").splitlines()[-1])
    assert saved["receipt_hash"] == row["receipt_hash"]
    assert saved["raw_audio_stored"] is False


def test_processing_gate_hash_chains_receipts(tmp_path, monkeypatch):
    monkeypatch.setattr(
        gate,
        "_sample_body",
        lambda state: {
            "interoception": {
                "cpu_load_norm": 0.1,
                "allostatic_load_norm": 0.2,
                "thermal_pressure": "Normal",
            },
            "metabolic": {
                "mode": "GREEN_GROW",
                "pressure": 0.1,
                "budget_multiplier": 0.9,
                "must_rest": False,
                "rest_seconds": 0.0,
            },
            "thermal": {"thermal_warning_level": 0, "thermal_pressure": "Normal"},
            "energy": {"charge_pct": 80.0, "low_power_mode": False},
        },
    )

    first = request_processing_clearance("ambient_text_memory_digest", state_dir=tmp_path)
    second = request_processing_clearance("ambient_text_memory_digest", state_dir=tmp_path)

    assert second["prev_hash"] == first["receipt_hash"]
    context = prompt_context(state_dir=tmp_path)
    assert "THERMODYNAMIC PROCESSING GATE" in context
    assert second["receipt_hash"][:12] in context


def test_processing_gate_charges_single_page_web_more_than_text(tmp_path, monkeypatch):
    monkeypatch.setattr(
        gate,
        "_sample_body",
        lambda state: {
            "interoception": {
                "cpu_load_norm": 0.1,
                "allostatic_load_norm": 0.2,
                "thermal_pressure": "Normal",
            },
            "metabolic": {
                "mode": "GREEN_GROW",
                "pressure": 0.1,
                "budget_multiplier": 0.9,
                "must_rest": False,
                "rest_seconds": 0.0,
            },
            "thermal": {"thermal_warning_level": 0, "thermal_pressure": "Normal"},
            "energy": {"charge_pct": 80.0, "low_power_mode": False},
        },
    )

    text = request_processing_clearance("ambient_text_memory_digest", state_dir=tmp_path)
    web = request_processing_clearance(
        "web.scrape_page",
        expected_value=0.8,
        payload={"url": "https://example.com"},
        state_dir=tmp_path,
    )

    assert web["allowed"] is True
    assert web["cost_class"] == "swimmer"
    assert web["estimated_stgm_cost"] > text["estimated_stgm_cost"]
    assert web["estimated_local_unit_cost"] > text["estimated_local_unit_cost"]


def test_processing_gate_defers_unbounded_internet_crawl_until_scoped(tmp_path, monkeypatch):
    monkeypatch.setattr(
        gate,
        "_sample_body",
        lambda state: {
            "interoception": {
                "cpu_load_norm": 0.1,
                "allostatic_load_norm": 0.2,
                "thermal_pressure": "Normal",
            },
            "metabolic": {
                "mode": "GREEN_GROW",
                "pressure": 0.1,
                "budget_multiplier": 0.9,
                "must_rest": False,
                "rest_seconds": 0.0,
            },
            "thermal": {"thermal_warning_level": 0, "thermal_pressure": "Normal"},
            "energy": {"charge_pct": 80.0, "low_power_mode": False},
        },
    )

    row = request_processing_clearance(
        "internet.crawl_unbounded",
        expected_value=0.99,
        state_dir=tmp_path,
    )

    assert row["allowed"] is False
    assert row["cleared"] is False
    assert row["clearance_state"] == "deferred"
    assert row["cost_class"] == "owner_scope"
    assert row["estimated_stgm_cost"] == 99.0
    assert "scope_unbounded_needs_owner_budget" in row["reasons"]


def test_processing_gate_marks_social_effector_as_breath_cost(tmp_path, monkeypatch):
    monkeypatch.setattr(
        gate,
        "_sample_body",
        lambda state: {
            "interoception": {
                "cpu_load_norm": 0.1,
                "allostatic_load_norm": 0.2,
                "thermal_pressure": "Normal",
            },
            "metabolic": {
                "mode": "GREEN_GROW",
                "pressure": 0.1,
                "budget_multiplier": 0.9,
                "must_rest": False,
                "rest_seconds": 0.0,
            },
            "thermal": {"thermal_warning_level": 0, "thermal_pressure": "Normal"},
            "energy": {"charge_pct": 80.0, "low_power_mode": False},
        },
    )

    row = request_processing_clearance(
        "whatsapp.send",
        expected_value=0.8,
        payload={"target": "Carlton"},
        state_dir=tmp_path,
    )

    assert row["allowed"] is True
    assert row["cost_class"] == "breath"
    assert row["estimated_stgm_cost"] == 0.1
