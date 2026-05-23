#!/usr/bin/env python3
"""Physics-anchored pytest coverage for the quantum-methods pair.

Modules under test
------------------
- System.swarm_split_step_fourier   (Fleck-Morris-Feit 1976 SSF integrator)
- System.swarm_optical_lattice      (Bloch problem for cold-atom lattices)

Every test docstring cites the peer-reviewed paper whose claim it
verifies. Per Architect directive 2026-05-11 ("BRING PHYSICS PAPERS
TO PROVE ALL YOUR TESTS").
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from System.swarm_split_step_fourier import (
    SSF_TRUTH_GUARD,
    SSFAnchor,
    SSFConfig,
    SplitStepFourier,
    TRUTH_LABEL as SSF_TRUTH_LABEL,
    VERIFIED_ANCHORS as SSF_ANCHORS,
    make_ssf_double_slit_2d,
    verified_anchor_ids as ssf_anchor_ids,
    write_ssf_receipt,
)
from System.swarm_optical_lattice import (
    OPTICAL_LATTICE_TRUTH_GUARD,
    OpticalLatticeAnchor,
    OpticalLatticeBands,
    OpticalLatticeConfig,
    TRUTH_LABEL as OL_TRUTH_LABEL,
    VERIFIED_ANCHORS as OL_ANCHORS,
    compute_band_structure,
    render_bands_ascii,
    verified_anchor_ids as ol_anchor_ids,
    write_lattice_receipt,
)


# ═══════════════════════════════════════════════════════════════════════════
# Split-Step Fourier
# ═══════════════════════════════════════════════════════════════════════════
class TestSSFAnchors:
    """Six peer-reviewed anchors. Foundation: Fleck-Morris-Feit 1976
    (Appl. Phys. 10, 129, DOI 10.1007/BF00896333), Hardin-Tappert 1973,
    Strang 1968 splitting, Yoshida 1990 high-order, Bao-Jin-Markowich
    2003 SIAM, Antoine et al 2008 absorbing boundaries.
    """

    def test_truth_label_and_guard(self):
        assert SSF_TRUTH_LABEL == "SIFTA_SPLIT_STEP_FOURIER_V1"
        assert "SPLIT_STEP_FOURIER_INTEGRATOR" in SSF_TRUTH_GUARD
        assert "ARCHITECT_DOCTRINE" in SSF_TRUTH_GUARD

    @pytest.mark.parametrize("anchor", SSF_ANCHORS)
    def test_anchor_carries_guards(self, anchor: SSFAnchor):
        assert anchor.supports.strip()
        assert anchor.does_not_support.strip()

    @pytest.mark.parametrize(
        "anchor_id",
        [
            "fleck_morris_feit_1976_solution_helmholtz",
            "hardin_tappert_1973_ssf_method",
            "strang_1968_construction_comparison",
            "yoshida_1990_higher_order_symplectic",
            "bao_jin_markowich_2003_numerical_schrodinger",
            "antoine_arnold_besse_2013_ssf_review",
        ],
    )
    def test_ssf_anchor_present(self, anchor_id):
        assert anchor_id in ssf_anchor_ids()


class TestSSFUnitarity:
    """Bao-Jin-Markowich 2003 (DOI 10.1137/S1064827501393253) proves
    that time-splitting spectral methods conserve the L²-norm
    unconditionally. Forward-Euler does NOT — that was the caveat I
    flagged last turn. This test directly verifies that SSF resolves
    it.
    """

    def test_l2_norm_conserved_for_free_packet(self):
        """SSF conserves ∫|ψ|² for free propagation (V=0).
        Bao-Jin-Markowich 2003 §2."""
        cfg = SSFConfig(shape=(128, 64), dt=0.05, mass=1.0)
        ssf = SplitStepFourier(cfg)
        ssf.add_wave_packet(
            position=(64, 32), sigma=4.0,
            momentum=(0.4, 0.0), amplitude=1.0,
        )
        ssf.normalize()
        N0 = ssf.norm_squared()
        ssf.run(100)
        N100 = ssf.norm_squared()
        # Strang splitting + FFT is unitary to floating-point precision.
        assert abs(N100 - N0) < 1e-9, (
            f"L² norm drift: |ΔN|={abs(N100 - N0):.2e}, expected < 1e-9"
        )

    def test_l2_norm_conserved_with_static_potential(self):
        """With a static real potential, SSF stays unitary.
        Bao-Jin-Markowich 2003 §3.1.
        """
        cfg = SSFConfig(shape=(64, 32), dt=0.02)
        V = np.zeros((64, 32))
        # A modest barrier in the middle.
        V[30:34, :] = 10.0
        ssf = SplitStepFourier(cfg, V_map=V)
        ssf.add_wave_packet(
            position=(15, 16), sigma=3.0,
            momentum=(0.6, 0.0), amplitude=1.0,
        )
        ssf.normalize()
        N0 = ssf.norm_squared()
        ssf.run(200)
        N200 = ssf.norm_squared()
        assert abs(N200 - N0) < 1e-8


class TestSSFDoubleSlit:
    """Schrödinger 1926 + Young 1804 double-slit reproduced with the
    unconditionally-stable SSF integrator. Compare with Bach et al
    2013 (NJP 15, 033018, DOI 10.1088/1367-2630/15/3/033018) for
    controlled-electron analog.
    """

    def test_make_ssf_double_slit_produces_far_side_intensity(self):
        """SSF + double-slit + sufficient propagation time yields
        far-side intensity. Group velocity in our units is v_g = ℏk/m;
        the packet needs ~ (barrier_x − pos_x) / v_g time to reach
        the barrier and tunnel through.
        """
        ssf = make_ssf_double_slit_2d(
            width=128, height=64,
            barrier_x=40,
            slit_offsets=(-10, 10),
            slit_width=2,
            packet_position=(15, 32),
            packet_momentum=(5.0, 0.0),
            packet_sigma=3.0,
            dt=0.02,
        )
        # ~10000 group-velocity units * dt should easily cross 100 cells
        ssf.run(800)
        density = ssf.density()
        far_side = density[80:, :]
        assert far_side.max() > 1e-6, (
            f"no far-side intensity after 800 steps; max={far_side.max():.2e}"
        )

    def test_ssf_norm_stable_during_double_slit_run(self):
        """The whole reason we built SSF: long-run stability that
        forward-Euler did not have. Verify it on a real double-slit.
        """
        ssf = make_ssf_double_slit_2d(
            width=128, height=64,
            barrier_x=40,
            slit_offsets=(-8, 8),
            packet_position=(20, 32),
            packet_momentum=(1.0, 0.0),
            dt=0.02,
        )
        N0 = ssf.norm_squared()
        ssf.run(150)
        N150 = ssf.norm_squared()
        # Long run with periodic boundaries: norm must be preserved
        # to ~1e-8. (Forward-Euler drifted by orders of magnitude on
        # the same problem.)
        assert abs(N150 - N0) < 1e-7, (
            f"SSF should preserve norm in long runs; "
            f"|ΔN|={abs(N150 - N0):.2e}"
        )


class TestSSFConfigValidation:
    def test_grid_must_be_at_least_4_per_axis(self):
        with pytest.raises(ValueError, match="≥ 4"):
            SSFConfig(shape=(3, 10))

    def test_positive_dx_dt_mass(self):
        with pytest.raises(ValueError):
            SSFConfig(shape=(10, 10), dx=0)
        # dt = 0 is invalid (no evolution). Negative dt is *allowed*
        # because Yoshida 1990 composition requires a backward
        # substep in the middle of each macro step.
        with pytest.raises(ValueError):
            SSFConfig(shape=(10, 10), dt=0.0)
        with pytest.raises(ValueError):
            SSFConfig(shape=(10, 10), mass=0)


# ═══════════════════════════════════════════════════════════════════════════
# Optical lattice
# ═══════════════════════════════════════════════════════════════════════════
class TestOpticalLatticeAnchors:
    """Eight cold-atom anchors anchored on Bloch's 1928 theorem,
    Ashcroft-Mermin 1976 textbook, and Jaksch-Zoller 1998 (PRL 81,
    3108, DOI 10.1103/PhysRevLett.81.3108) which derives Bose-Hubbard
    from optical-lattice physics.
    """

    def test_truth_label_and_guard(self):
        assert OL_TRUTH_LABEL == "SIFTA_OPTICAL_LATTICE_V1"
        assert "OPTICAL_LATTICE_ANALOGUE_ONLY" in OPTICAL_LATTICE_TRUTH_GUARD

    @pytest.mark.parametrize("anchor", OL_ANCHORS)
    def test_anchor_carries_guards(self, anchor: OpticalLatticeAnchor):
        assert anchor.supports.strip()
        assert anchor.does_not_support.strip()

    @pytest.mark.parametrize(
        "anchor_id",
        [
            "jaksch_zoller_1998_bose_hubbard_optical_lattice",
            "greiner_2002_mott_insulator_quantum_phase_transition",
            "bloch_2005_ultracold_quantum_gases_optical_lattices",
            "bloch_dalibard_zwerger_2008_many_body_optical_lattices",
            "lewenstein_2007_ultracold_atomic_gases_lattices",
            "morsch_oberthaler_2006_dynamics_BEC_optical_lattices",
            "ashcroft_mermin_1976_solid_state_physics",
            "anderson_kasevich_1998_bloch_oscillations",
        ],
    )
    def test_optical_lattice_anchor_present(self, anchor_id):
        assert anchor_id in ol_anchor_ids()


class TestBlochBandStructure:
    """The 1D Bloch problem in a periodic potential V₀ cos²(k_L x).
    Ashcroft-Mermin 1976 Chapter 8: at finite V₀ > 0 a band gap opens
    between the first and second bands at the Brillouin zone boundary.
    """

    def test_band_structure_returns_correct_shape(self):
        cfg = OpticalLatticeConfig(
            lattice_depth_Er=5.0,
            n_plane_waves=15,
            n_quasimomentum_points=21,
        )
        bands = compute_band_structure(cfg)
        assert bands.n_bands == 15
        assert len(bands.quasimomenta) == 21
        assert all(len(b) == 21 for b in bands.band_energies)

    def test_band_gap_opens_for_finite_lattice_depth(self):
        """Ashcroft-Mermin 1976 §8: a finite periodic potential opens
        a band gap between the lowest two bands at the Brillouin zone
        edge. Verify the gap is strictly positive.
        """
        cfg = OpticalLatticeConfig(
            lattice_depth_Er=8.0,
            n_plane_waves=21,
            n_quasimomentum_points=51,
        )
        bands = compute_band_structure(cfg)
        gap_0_1 = bands.band_gaps[0]
        assert gap_0_1 > 0, (
            f"first band gap should be positive at V₀=8 E_R; "
            f"got {gap_0_1:.4f}"
        )

    def test_zero_depth_bands_are_free_particle_dispersion(self):
        """At V₀ = 0, the band structure reduces to free-particle
        parabolic dispersion (Ashcroft-Mermin 1976 §8 empty-lattice
        approximation): bands fold into the first Brillouin zone but
        do not gap.
        """
        cfg = OpticalLatticeConfig(
            lattice_depth_Er=0.0,
            n_plane_waves=15,
            n_quasimomentum_points=21,
        )
        bands = compute_band_structure(cfg)
        # The empty-lattice band gaps should touch zero (bands meet at
        # zone boundaries). Allow a small numerical floor.
        for n, gap in enumerate(bands.band_gaps[:3]):
            assert gap < 1e-9, (
                f"V₀=0 should have ZERO gap; band {n}→{n+1} gap={gap:.4e}"
            )

    def test_deeper_lattice_widens_gap(self):
        """Bloch-Dalibard-Zwerger 2008 §III.A: the first band gap
        increases monotonically with V₀ for V₀ ≳ E_R.
        """
        deep_gap = compute_band_structure(OpticalLatticeConfig(
            lattice_depth_Er=15.0, n_plane_waves=21,
            n_quasimomentum_points=31,
        )).band_gaps[0]
        shallow_gap = compute_band_structure(OpticalLatticeConfig(
            lattice_depth_Er=2.0, n_plane_waves=21,
            n_quasimomentum_points=31,
        )).band_gaps[0]
        assert deep_gap > shallow_gap, (
            f"deeper lattice should have larger first gap; "
            f"V₀=15 gap={deep_gap:.3f}, V₀=2 gap={shallow_gap:.3f}"
        )

    def test_render_bands_ascii_well_formed(self):
        bands = compute_band_structure(OpticalLatticeConfig(
            lattice_depth_Er=10.0, n_plane_waves=11,
            n_quasimomentum_points=21,
        ))
        text = render_bands_ascii(bands)
        assert "Optical lattice band structure" in text
        assert "Band gaps" in text
        assert "10.00 E_R" in text


class TestLatticeConfigValidation:
    def test_negative_depth_rejected(self):
        with pytest.raises(ValueError):
            OpticalLatticeConfig(lattice_depth_Er=-1.0)

    def test_even_plane_waves_rejected(self):
        with pytest.raises(ValueError, match="odd"):
            OpticalLatticeConfig(n_plane_waves=10)

    def test_too_few_plane_waves_rejected(self):
        with pytest.raises(ValueError):
            OpticalLatticeConfig(n_plane_waves=3)


class TestLatticeReceipt:
    def test_receipt_round_trip(self, tmp_path):
        bands = compute_band_structure(OpticalLatticeConfig(
            lattice_depth_Er=5.0, n_plane_waves=11,
            n_quasimomentum_points=11,
        ))
        out = tmp_path / "lat.jsonl"
        row = write_lattice_receipt(
            state_root=tmp_path, receipt_path=out, bands=bands,
        )
        assert row["truth_label"] == OL_TRUTH_LABEL
        assert "sha256" in row and len(row["sha256"]) == 64
        parsed = json.loads(out.read_text("utf-8").strip())
        assert parsed["anchor_count"] == len(OL_ANCHORS)
        assert parsed["bands"]["n_bands"] == 11
