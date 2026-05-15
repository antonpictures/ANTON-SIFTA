import json
from pathlib import Path

from System.swarm_higgs_vicsek_observatory import (
    LEDGER_NAME,
    TRUTH_BOUNDARY,
    TRUTH_LABEL,
    build_engine_c_payload,
    render_engine_c_summary,
    write_engine_c_receipt,
)


def test_engine_c_payload_combines_vicsek_and_higgs_without_qt():
    payload = build_engine_c_payload(
        noises=(0.1, 6.0),
        vicsek_particles=80,
        vicsek_burn_in_steps=80,
        vicsek_average_steps=30,
        higgs_steps=120,
    )

    assert payload["truth_label"] == TRUTH_LABEL
    assert payload["simulated"] is True
    assert payload["no_particle_physics_claim"] is True
    assert "No OBSERVED Higgs bosons" in payload["truth_boundary"]
    assert payload["summary"]["vicsek_order_drop"] > 0.25
    assert payload["summary"]["higgs_order_parameter"] > 0.7
    assert payload["summary"]["strongest_swimmer_mass"] > payload["summary"]["weakest_swimmer_mass"]


def test_engine_c_receipt_writes_truth_boundary(tmp_path):
    payload = build_engine_c_payload(
        noises=(0.1, 6.0),
        vicsek_particles=50,
        vicsek_burn_in_steps=40,
        vicsek_average_steps=20,
        higgs_steps=100,
    )
    receipt = write_engine_c_receipt(payload, state_root=tmp_path)

    assert receipt["truth_label"] == TRUTH_LABEL
    assert receipt["truth_boundary"] == TRUTH_BOUNDARY
    rows = [
        json.loads(line)
        for line in (tmp_path / LEDGER_NAME).read_text(encoding="utf-8").splitlines()
    ]
    assert rows[0]["payload"]["truth_boundary"] == TRUTH_BOUNDARY
    assert rows[0]["payload"]["no_particle_physics_claim"] is True


def test_engine_c_summary_names_both_mechanisms():
    payload = build_engine_c_payload(
        noises=(0.1, 6.0),
        vicsek_particles=50,
        vicsek_burn_in_steps=40,
        vicsek_average_steps=20,
        higgs_steps=100,
    )
    text = render_engine_c_summary(payload)

    assert "Vicsek" in text
    assert "Higgs" in text
    assert "Classical SIFTA analogues only" in text


def test_physics_observatory_source_exposes_engine_c_tab_without_importing_qt():
    source = Path("Applications/sifta_physics_observatory.py").read_text(encoding="utf-8")

    assert "Engine C — Swarm Field / Higgs-Vicsek" in source
    assert "Run Proof + Receipt" in source
    assert "write_engine_c_receipt" in source


def test_physics_observatory_has_experiment_governor_without_importing_qt():
    source = Path("Applications/sifta_physics_observatory.py").read_text(encoding="utf-8")

    assert "Ready — one experiment at a time" in source
    assert "_begin_experiment" in source
    assert "_stop_current_experiment" in source
    assert "currentChanged.connect(self._on_tab_changed)" in source
    assert "wait for Ready before switching experiments" in source
