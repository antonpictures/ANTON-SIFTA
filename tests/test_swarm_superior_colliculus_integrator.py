"""Tests for superior colliculus → body_brain multisensory bridge."""
from __future__ import annotations

import json
from pathlib import Path

from System import swarm_superior_colliculus_integrator as sci


def _tick() -> dict:
    return {
        "event": "body_brain_tick",
        "tick_id": "bb-sc-1",
        "td_value": 0.35,
        "action": {"type": "explore", "target": "test"},
        "result": {"status": "completed", "latency": 0.05, "energy_used": 0.02},
    }


def test_weak_bimodal_inverse_effectiveness_boost() -> None:
    visual = {"u_stigmergic_drive": 0.15, "u_metabolic_scope": 0.3, "u_heading": 0.0, "ts": 1000.0}
    audio = {"acoustic_stress": 0.12, "acoustic_danger_proxy": 0.05, "cochlea_ts": 1000.01}
    m = sci.compute_integrated_salience(visual, audio, 0.0, owl_ts=None)
    assert m["inverse_effectiveness"] > 2.0
    assert m["integrated_salience"] > 0.85


def test_temporal_misalignment_reduces_salience() -> None:
    visual = {"u_stigmergic_drive": 0.4, "u_metabolic_scope": 0.6, "u_heading": 0.0, "ts": 0.0}
    audio_close = {"acoustic_stress": 0.35, "acoustic_danger_proxy": 0.1, "cochlea_ts": 0.05}
    audio_far = {"acoustic_stress": 0.35, "acoustic_danger_proxy": 0.1, "cochlea_ts": 10.0}
    close = sci.compute_integrated_salience(visual, audio_close, 0.0)["integrated_salience"]
    far = sci.compute_integrated_salience(visual, audio_far, 0.0)["integrated_salience"]
    assert close > far


def test_spatial_mismatch_reduces_salience() -> None:
    visual = {"u_stigmergic_drive": 0.5, "u_metabolic_scope": 0.7, "u_heading": 0.0, "ts": 500.0}
    audio = {"acoustic_stress": 0.45, "acoustic_danger_proxy": 0.1, "cochlea_ts": 500.0}
    aligned = sci.compute_integrated_salience(visual, audio, 0.0)["integrated_salience"]
    mis = sci.compute_integrated_salience(visual, audio, 2.2)["integrated_salience"]
    assert aligned >= mis


def test_integrate_to_body_brain_raises_td(tmp_path: Path) -> None:
    phen = tmp_path / "visual_phenotype_uniforms.jsonl"
    phen.write_text(
        json.dumps(
            {
                "ts": 2000.0,
                "u_stigmergic_drive": 0.25,
                "u_metabolic_scope": 0.6,
                "u_heading": 0.1,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    coch = tmp_path / "stigmergic_cochlea.jsonl"
    coch.write_text(
        json.dumps(
            {
                "ts": 2000.02,
                "tick_id": "c-x",
                "acoustic_stress": 0.3,
                "td_bias": 0.0,
                "danger_hint": "ACOUSTIC_FEATURES_NOMINAL",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    owl = tmp_path / "owl_spatial_hearing.jsonl"
    owl.write_text(
        json.dumps({"timestamp": 2000.01, "azimuth_rad": 0.12, "truth_label": "SIMULATED_SPATIAL_HEARING"})
        + "\n",
        encoding="utf-8",
    )
    mem = tmp_path / "body_brain_memory.jsonl"
    base = _tick()
    out = sci.integrate_to_body_brain(
        base,
        phenotype_path=phen,
        cochlea_ledger=coch,
        owl_path=owl,
        state_root=tmp_path,
    )
    assert out["td_value"] > base["td_value"]
    assert out["tick_source"] == "superior_colliculus_integrator"
    assert out["truth_label"] == sci.TRUTH_MULTISENSORY
    sci.append_integrated_tick(out, memory_path=mem, state_root=tmp_path)
    assert mem.read_text(encoding="utf-8").strip()


def test_missing_modal_receipts_do_not_raise_td(tmp_path: Path) -> None:
    base = _tick()
    out = sci.integrate_to_body_brain(base, state_root=tmp_path)

    assert out["td_value"] == base["td_value"]
    assert out["collicular_salience"] == 0.0
    assert out["multisensory_integrated"] is False
    assert out["colliculus_overlay_status"] == sci.STATUS_NO_MULTISENSORY_RECEIPT
    assert out["visual_receipt_backed"] is False
    assert out["cochlea_receipt_backed"] is False


def test_invalid_uniform_numbers_are_bounded(tmp_path: Path) -> None:
    phen = tmp_path / "visual_phenotype_uniforms.jsonl"
    phen.write_text(
        json.dumps({"ts": 10.0, "u_stigmergic_drive": "bad", "u_metabolic_scope": 4.0, "u_heading": "nan"})
        + "\n",
        encoding="utf-8",
    )
    visual = sci.read_latest_visual_uniforms(phenotype_path=phen, state_root=tmp_path)

    assert visual["u_stigmergic_drive"] == 0.2
    assert visual["u_metabolic_scope"] == 1.0
    assert visual["u_heading"] == 0.0
