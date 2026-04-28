#!/usr/bin/env python3
"""
tests/test_swarm_gecko_adhesion.py
Proof bar for the Gecko Adhesion Organ (Event 75a).
Truth: REAL_CPU on Apple Silicon (no CUDA).
"""
import math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.swarm_gecko_adhesion import (
    compute_adhesion, warp_truth_probe, explain,
    TRUTH_REAL_GPU, TRUTH_REAL_CPU, TRUTH_STUB, TRUTH_BROKEN,
    _WARP_TRUTH,
)


def test_warp_probe_returns_dict():
    p = warp_truth_probe()
    assert "truth" in p
    assert p["truth"] in (TRUTH_REAL_GPU, TRUTH_REAL_CPU, TRUTH_STUB, TRUTH_BROKEN)


def test_warp_truth_is_real_on_this_machine():
    """Warp 1.12.1 is installed — should be at least REAL_CPU."""
    assert _WARP_TRUTH in (TRUTH_REAL_CPU, TRUTH_REAL_GPU), (
        f"Warp installed but truth={_WARP_TRUTH!r} — check import"
    )


def test_compute_adhesion_returns_receipt():
    r = compute_adhesion(z_values=[3.0, 2.0, 1.0, 0.5], write_receipt=False)
    assert r.n_probes == 4
    assert r.truth in (TRUTH_REAL_CPU, TRUTH_REAL_GPU, TRUTH_BROKEN)


def test_adhesion_zone_physics():
    """Probes far from surface should be in adhesion zone (F < 0)."""
    r = compute_adhesion(z_values=[5.0, 3.0, 2.0], write_receipt=False)
    # All three probes should be attractive (vdW dominates at these gaps)
    for f in r.f_net_values:
        assert f < 0, f"Expected adhesion (F<0) at safe gap, got F={f}"


def test_repulsion_at_zero_gap():
    """Very small gap triggers LJ repulsion (F > 0)."""
    r = compute_adhesion(z_values=[0.26], write_receipt=False)  # just above floor
    assert r.f_net_values[0] > 0, (
        f"Expected repulsion at z≈0.26, got F={r.f_net_values[0]}"
    )


def test_max_adhesion_negative():
    r = compute_adhesion(write_receipt=False)
    assert r.adhesion_count > 0
    assert r.max_adhesion < 0


def test_force_increases_as_probe_approaches():
    """Force magnitude (adhesion) grows as probe approaches surface."""
    zs = [4.0, 3.0, 2.0, 1.0]
    r = compute_adhesion(z_values=zs, write_receipt=False)
    fs = r.f_net_values
    # Each step closer should have more negative force (stronger adhesion)
    for i in range(len(fs) - 1):
        if fs[i] < 0 and fs[i+1] < 0:
            assert fs[i+1] < fs[i], (
                f"Adhesion should strengthen as z decreases: f[{i}]={fs[i]}, f[{i+1}]={fs[i+1]}"
            )


def test_explain_contains_truth():
    s = explain()
    assert _WARP_TRUTH in s
    assert "NPPL" in s
    assert "Autumn" in s


def test_default_run_produces_20_probes():
    r = compute_adhesion(write_receipt=False)
    assert r.n_probes == 20


def test_receipt_fields_complete():
    r = compute_adhesion(write_receipt=False)
    assert r.ts > 0
    assert r.warp_version is not None
    assert "NPPL" in r.notes
    assert "Autumn" in r.notes
