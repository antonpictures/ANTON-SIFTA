from __future__ import annotations

import math

import numpy as np

from System.swarm_sar_triage_organ import triage
from System.swarm_turbulence_organ import run_swarm
from System.swarm_turbulence_substrate import TurbulenceParams, degrade, synthetic_target


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
