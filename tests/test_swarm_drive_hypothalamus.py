"""Drive hypothalamus — goal pressure and basal ganglia priors."""

from __future__ import annotations

import json
from pathlib import Path

from System.swarm_drive_hypothalamus import (
    DriveHypothalamus,
    metabolic_sufficiency,
)


def test_metabolic_sufficiency_from_fraction() -> None:
    assert metabolic_sufficiency({"energy_fraction": 0.25}) == 0.25
    assert metabolic_sufficiency({"energy_pct": 80.0}) == 0.8


def test_energy_drive_rises_when_starved() -> None:
    h = DriveHypothalamus()
    snap = h.update({"energy_fraction": 0.2}, {})
    assert snap.drives["energy"] > 1.0
    assert snap.metabolic_sufficiency == 0.2


def test_owner_activity_boosts_social() -> None:
    h = DriveHypothalamus()
    h.update({"energy_fraction": 0.9}, {"owner_activity": True})
    assert h.drives["social"] == 1.0


def test_errors_boost_safety() -> None:
    h = DriveHypothalamus()
    h.update({"energy_fraction": 0.5}, {"errors": True})
    assert h.drives["safety"] == 1.0
    h.update({"energy_fraction": 0.5}, {"errors": False})
    assert h.drives["safety"] == 0.3


def test_dominant_drive() -> None:
    h = DriveHypothalamus(initial={"curiosity": 2.0, "social": 0.1, "energy": 0.1, "safety": 0.1})
    assert h.dominant_drive() == "curiosity"


def test_basal_ganglia_deltas_keys() -> None:
    h = DriveHypothalamus()
    h.update({"energy_fraction": 0.5}, {"owner_activity": True})
    d = h.basal_ganglia_score_deltas()
    assert set(d.keys()) >= {"SILENCE", "TOOL", "ENGAGE", "BOND"}


def test_append_ledger(tmp_path: Path) -> None:
    h = DriveHypothalamus()
    snap = h.update({"energy_fraction": 0.6}, {})
    path = h.append_ledger(snap, state_dir=tmp_path)
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    row = json.loads(lines[-1])
    assert row["dominant"] == snap.dominant
    assert "drives" in row
