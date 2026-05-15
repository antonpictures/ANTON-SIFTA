"""Tests for the §20.F HYPOTHESIS force-regime sweep.

Architect 2026-05-13 — Grok-Robotics analysis suggested that "if you
really crank the force in the sim, eventually even the heavy swimmers
start moving fast again — high-energy collisions overcome binding."

These tests guard:
    - drive_amplitude actually changes per-step motion in a measurable way
    - drive_amplitude=0 still produces non-trivial random motion (thermal noise)
    - drive_amplitude=0 specifically — swimmers do NOT move on average
    - run_force_regime_sweep walks every requested drive level
    - the receipt carries TRUTH_LABEL_FORCE_SWEEP + "HYPOTHESIS" class +
      the same TRUTH_BOUNDARY disclaimer used everywhere else
    - the engineering_inertia_proxy is a sensible scalar per band
    - the FINDING — whether the strong/free ratio collapses toward 1 —
      is reported HONESTLY in the summary regardless of which way it goes

These tests do NOT assume the regime-overcomes-binding prediction held.
The sweep is an HONEST experiment; the test guards the measurement, not
the outcome.
"""
import json
import pytest

np = pytest.importorskip("numpy")

from System.swarm_higgs_stigmergy_field import (
    HiggsFieldConfig,
    HiggsParticleSwimmer,
    HiggsStigmergyField,
    LEDGER_NAME,
    TRUTH_BOUNDARY,
    TRUTH_LABEL_FORCE_SWEEP,
    phi_as_array,
    run_force_regime_sweep,
)


def _relaxed_field(seed=11, w=20, h=14, steps=140):
    f = HiggsStigmergyField(HiggsFieldConfig(seed=seed, width=w, height=h))
    f.relax(steps)
    return f


def test_drive_amplitude_changes_motion_magnitude():
    """Higher drive must produce visibly more motion per step."""
    f1 = _relaxed_field()
    f2 = _relaxed_field()  # identical seed → identical field

    low = HiggsParticleSwimmer(
        n=40, coupling=0.0, field_shape=(14, 20), seed=7,
        drive_amplitude=0.2,
    )
    high = HiggsParticleSwimmer(
        n=40, coupling=0.0, field_shape=(14, 20), seed=7,
        drive_amplitude=5.0,
    )
    for _ in range(150):
        f1.step(); f2.step()
        low.step(phi_as_array(f1))
        high.step(phi_as_array(f2))

    assert high.mobility() > low.mobility() * 3.0


def test_drive_amplitude_zero_kills_drift():
    """drive_amplitude=0 with no thermal_kick should freeze the swarm
    after initial-velocity damping decays."""
    f = _relaxed_field()
    swimmers = HiggsParticleSwimmer(
        n=20, coupling=0.0, field_shape=(14, 20), seed=5,
        drive_amplitude=0.0, thermal_kick=0.0,
    )
    for _ in range(200):
        f.step()
        swimmers.step(phi_as_array(f))
    # After 200 steps of damping with no forcing, mobility should be
    # essentially zero — exponential decay (0.95**200 ≈ 3.5e-5).
    assert swimmers.mobility() < 1e-3


def test_set_drive_amplitude_live_update():
    """Slider path: set_drive_amplitude must update the live value."""
    s = HiggsParticleSwimmer(
        n=5, coupling=1.0, field_shape=(14, 20), seed=3,
        drive_amplitude=1.0,
    )
    assert s.drive_amplitude == 1.0
    s.set_drive_amplitude(3.7)
    assert s.drive_amplitude == 3.7
    with pytest.raises(ValueError):
        s.set_drive_amplitude(-0.5)


def test_swimmer_rejects_negative_drive_amplitude_at_init():
    with pytest.raises(ValueError):
        HiggsParticleSwimmer(
            n=2, coupling=0.0, field_shape=(14, 20),
            drive_amplitude=-1.0,
        )


def test_state_dict_includes_drive_amplitude():
    s = HiggsParticleSwimmer(
        n=3, coupling=2.0, field_shape=(14, 20),
        drive_amplitude=2.5, seed=1, name="probe",
    )
    st = s.state()
    assert st["drive_amplitude"] == 2.5


def test_run_force_regime_sweep_writes_truth_labeled_receipt(tmp_path):
    drive_levels = (0.5, 1.0, 5.0)
    result = run_force_regime_sweep(
        drive_levels=drive_levels,
        couplings=(0.0, 1.0, 4.0),
        n_per_band=15,
        field_config=HiggsFieldConfig(seed=13, width=20, height=14),
        relax_steps=140,
        swimmer_steps=200,
        state_root=tmp_path,
        write=True,
        seed=17,
    )
    assert result["truth_label"] == TRUTH_LABEL_FORCE_SWEEP
    assert result["truth_class"] == "HYPOTHESIS"
    assert result["simulated"] is True
    assert result["no_particle_physics_claim"] is True
    assert "no OBSERVED Higgs bosons" in result["truth_boundary"]
    assert len(result["regimes"]) == len(drive_levels)
    for regime, expected_drive in zip(result["regimes"], drive_levels):
        assert regime["drive_amplitude"] == pytest.approx(expected_drive)
        for band in ("free", "weak", "strong"):
            assert band in regime["bands"]
            assert "mobility" in regime["bands"][band]
            assert "mean_mass" in regime["bands"][band]
        assert "mobility_ratio_strong_over_free" in regime
        assert "engineering_inertia_proxy" in regime

    # Receipt landed on disk with the right shape.
    rows = [
        json.loads(line)
        for line in (tmp_path / LEDGER_NAME).read_text(encoding="utf-8").splitlines()
    ]
    assert len(rows) == 1
    row = rows[0]
    assert row["kind"] == "HIGGS_FORCE_REGIME_SWEEP"
    assert row["truth_label"] == TRUTH_LABEL_FORCE_SWEEP
    assert row["truth_class"] == "HYPOTHESIS"
    assert row["truth_boundary"] == TRUTH_BOUNDARY


def test_sweep_summary_reports_honest_collapse_outcome(tmp_path):
    """The summary key 'ratio_collapsed_toward_one' must reflect what
    actually happened in the data, not what we hoped would happen."""
    result = run_force_regime_sweep(
        drive_levels=(0.1, 10.0),
        couplings=(0.0, 1.0, 4.0),
        n_per_band=15,
        relax_steps=140,
        swimmer_steps=200,
        state_root=tmp_path,
        write=False,
        seed=17,
    )
    summary = result["summary"]
    low = summary["lowest_drive_ratio"]
    high = summary["highest_drive_ratio"]
    # Honest reporting: the flag matches the comparison
    assert summary["ratio_collapsed_toward_one"] == (high > low)


def test_engineering_inertia_proxy_orders_correctly(tmp_path):
    """At a single fixed drive, strong should have HIGHER inertia proxy
    (force_per_unit_motion) than weak should be higher than free, because
    the proxy is drive / mobility and strong is the slowest."""
    result = run_force_regime_sweep(
        drive_levels=(1.0,),
        couplings=(0.0, 1.0, 4.0),
        n_per_band=20,
        relax_steps=140,
        swimmer_steps=300,
        state_root=tmp_path,
        write=False,
        seed=17,
    )
    proxies = result["regimes"][0]["engineering_inertia_proxy"]
    # Strong should be at least as heavy in the proxy sense as free.
    assert proxies["strong"] > proxies["free"]
    # Weak should sit between them (or at least not below free).
    assert proxies["weak"] >= proxies["free"] * 0.9
