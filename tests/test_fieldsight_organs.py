from __future__ import annotations

import math
import os

import numpy as np

from System.swarm_sar_triage_organ import triage
from System.swarm_turbulence_organ import run_swarm
from System.swarm_turbulence_substrate import TurbulenceParams, degrade, synthetic_target

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_turbulence_substrate_preserves_psf_energy():
    img = synthetic_target(kind="rescue_hiker", grid=64)
    params = TurbulenceParams(cn2=6e-15)
    degraded, psf = degrade(img, params=params, seed=7, noise_sigma=0.0)

    assert degraded.shape == img.shape
    assert psf.shape == img.shape
    assert math.isclose(float(psf.sum()), 1.0, rel_tol=1e-6, abs_tol=1e-6)
    assert params.r0 > 0.0


def test_sar_triage_flags_synthetic_rescue_target_not_noise():
    target = synthetic_target(kind="rescue_hiker", grid=64)
    target_result = triage(target, positions_per_axis=5, write_ledger=False)

    noise = np.random.default_rng(123).normal(0.5, 0.04, (64, 64))
    noise_result = triage(np.clip(noise, 0.0, 1.0), positions_per_axis=5, write_ledger=False)

    assert target_result.target_present is True
    assert target_result.triage_score > noise_result.triage_score


def test_fieldsight_chained_swarm_returns_finite_posterior():
    img = synthetic_target(kind="rescue_hiker", grid=64)
    params = TurbulenceParams(cn2=6e-15)
    degraded, _ = degrade(img, params=params, seed=11, noise_sigma=0.005)

    result = run_swarm(
        degraded,
        n_swimmers=8,
        r0_grid_m=list(np.geomspace(0.008, 0.2, 8)),
        ticks=2,
        planted_params=params,
        write_ledger=False,
    )

    assert result.posterior_mean_r0_m > 0.0
    assert math.isfinite(result.posterior_mean_cn2)
    assert len(result.swimmers) == 8
    assert any(sw.pheromone > 0 for sw in result.swimmers)


def test_fieldsight_widget_surfaces_gamma_posterior_and_swimmer_census():
    from PyQt6.QtWidgets import QApplication

    from Applications.sifta_fieldsight_widget import SiftaFieldSightWidget

    app = QApplication.instance() or QApplication([])
    widget = SiftaFieldSightWidget()
    try:
        row = widget._compute_demo()
        gamma = row.get("gamma_posterior") or {}

        assert gamma
        assert gamma.get("deferred_by_thermodynamics") is not True
        assert gamma["posterior_mean_gamma"] > 0.0
        assert gamma["posterior_std_gamma"] >= 0.0
        assert gamma["thermodynamic_clearance"]["allowed"] is True
        assert gamma["swimmer_census"]["swimmer_count"] == len(gamma["swimmers"])
        assert gamma["swimmer_census"]["unaccounted_swimmers"] == 0
        assert gamma["swimmer_census"]["all_swimmers_accounted"] is True

        metrics = widget._format_metrics(row)
        assert "gamma posterior:" in metrics
        assert "gamma thermo:" in metrics
        assert "gamma swimmers:" in metrics
    finally:
        widget.deleteLater()
        app.processEvents()


def test_fieldsight_optional_body_slit_reports_no_unaccounted_swimmers():
    from PyQt6.QtWidgets import QApplication

    from Applications.sifta_fieldsight_widget import SiftaFieldSightWidget

    app = QApplication.instance() or QApplication([])
    widget = SiftaFieldSightWidget()
    try:
        widget._slit_coh.setChecked(True)
        row = widget._compute_demo()
        slit = row.get("slit_coherence") or {}

        assert slit
        assert "error" not in slit
        assert slit["thermodynamic_clearance"]["allowed"] is True
        assert slit["swimmer_census"]["unaccounted_swimmers"] == 0
        assert slit["swimmer_census"]["all_swimmers_accounted"] is True
        assert slit["body_swimmer_census"]["unaccounted_swimmers"] == 0
        assert slit["body_swimmer_census"]["all_swimmers_accounted"] is True

        metrics = widget._format_metrics(row)
        assert "slit swimmers:" in metrics
        assert "unaccounted=0" in metrics
    finally:
        widget.deleteLater()
        app.processEvents()
