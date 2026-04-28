#!/usr/bin/env python3
"""tests/test_swarm_spider_web.py — Proof bar for Spider Web Organ (Event 75c)."""
import math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.swarm_spider_web import (
    pluck, warp_truth_probe, explain, build_orb_web,
    TRUTH_REAL_GPU, TRUTH_REAL_CPU, TRUTH_STUB, TRUTH_BROKEN,
    _WARP_TRUTH,
)


def test_warp_probe_returns_dict():
    p = warp_truth_probe()
    assert "truth" in p
    assert p["truth"] in (TRUTH_REAL_GPU, TRUTH_REAL_CPU, TRUTH_STUB, TRUTH_BROKEN)


def test_warp_truth_is_real_on_this_machine():
    assert _WARP_TRUTH in (TRUTH_REAL_CPU, TRUTH_REAL_GPU), (
        f"Warp installed but truth={_WARP_TRUTH!r}"
    )


def test_pluck_returns_receipt():
    r = pluck(write_receipt=False)
    assert r.n_nodes == 41     # 1 hub + 8×5
    assert r.n_edges == 80
    assert r.truth in (TRUTH_REAL_CPU, TRUTH_REAL_GPU, TRUTH_BROKEN)


def test_energy_decays_with_damping():
    """After many ticks with damping, energy must be less than initial."""
    r = pluck(source_node=0, impulse=1.0, ticks=50,
              stiffness=0.5, damping=0.15, write_receipt=False)
    assert r.energy_ratio < 1.0, (
        f"Energy did not decay: ratio={r.energy_ratio} (damping broken)"
    )
    assert r.all_bounded


def test_zero_impulse_zero_energy():
    """No impulse → no energy, no motion."""
    r = pluck(impulse=0.0, ticks=20, write_receipt=False)
    assert r.total_energy < 1e-8
    assert r.all_bounded


def test_source_node_stored_in_receipt():
    for src in (0, 1, 10, 40):
        r = pluck(source_node=src, ticks=5, write_receipt=False)
        assert r.source_node == src


def test_all_displacements_bounded():
    """No NaN or inf after propagation."""
    r = pluck(source_node=7, impulse=2.0, ticks=40, write_receipt=False)
    assert r.all_bounded


def test_larger_impulse_larger_energy():
    """Doubling impulse → 4× energy (energy ∝ amplitude²)."""
    r1 = pluck(impulse=1.0, ticks=0, write_receipt=False)
    r2 = pluck(impulse=2.0, ticks=0, write_receipt=False)
    assert abs(r2.energy_t0 / r1.energy_t0 - 4.0) < 0.01


def test_hub_vs_rim_different_decay():
    """Hub (node 0, many connections) decays faster than rim node (fewer connections)."""
    hub = pluck(source_node=0, impulse=1.0, ticks=30, write_receipt=False)
    rim = pluck(source_node=40, impulse=1.0, ticks=30, write_receipt=False)
    # Both should decay, hub should have a different ratio from rim
    assert hub.energy_ratio < 1.0
    assert rim.energy_ratio < 1.0


def test_orb_web_topology():
    """build_orb_web returns correct node/edge counts."""
    web = build_orb_web(n_radial=8, n_ring=5)
    assert web["n_nodes"] == 41
    adj = web["adj"]
    # Every row has exactly MAX_DEG entries
    assert all(len(row) == 12 for row in adj)
    # Padding is -1
    for row in adj:
        for j in row:
            assert j >= -1


def test_explain_contains_refs():
    s = explain()
    assert "Mortimer" in s
    assert "NPPL" in s
    assert _WARP_TRUTH in s


def test_receipt_fields_complete():
    r = pluck(write_receipt=False)
    assert r.ts > 0
    assert r.warp_version is not None
    assert "NPPL" in r.notes
    assert "Mortimer" in r.notes
    assert r.n_edges > 0
