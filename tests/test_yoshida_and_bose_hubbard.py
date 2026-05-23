#!/usr/bin/env python3
"""Physics-anchored pytest coverage for Yoshida-4 splitting and the
Bose-Hubbard small-system module.

Every test docstring cites the peer-reviewed paper whose claim it
verifies. Per Architect directive: BRING PHYSICS PAPERS TO PROVE ALL
YOUR TESTS.
"""
from __future__ import annotations

import math
import numpy as np
import pytest

from System.swarm_split_step_fourier import SSFConfig, SplitStepFourier
from System.swarm_yoshida_splitting import (
    TRUTH_LABEL as YO_TRUTH_LABEL,
    VERIFIED_ANCHORS as YO_ANCHORS,
    YOSHIDA_W0,
    YOSHIDA_W1,
    YOSHIDA_WEIGHTS,
    YOSHIDA_TRUTH_GUARD,
    YoshidaAnchor,
    YoshidaSSF,
    verified_anchor_ids as yo_anchor_ids,
)
from System.swarm_bose_hubbard import (
    BOSE_HUBBARD_TRUTH_GUARD,
    BHGroundState,
    BoseHubbardAnchor,
    BoseHubbardConfig,
    TRUTH_LABEL as BH_TRUTH_LABEL,
    VERIFIED_ANCHORS as BH_ANCHORS,
    compute_ground_state,
    render_scan_ascii,
    superfluid_mott_scan,
    verified_anchor_ids as bh_anchor_ids,
)


# ═══════════════════════════════════════════════════════════════════════════
# Yoshida 4th-order splitting
# ═══════════════════════════════════════════════════════════════════════════
class TestYoshidaWeights:
    """Yoshida 1990 (Phys. Lett. A 150, 262, DOI 10.1016/0375-9601(90)
    90092-3) equation (4.6): the unique weights w_1 = 1/(2 − 2^(1/3))
    and w_0 = 1 − 2 w_1 produce 4th-order symmetric composition.
    """

    def test_weights_sum_to_one(self):
        """Time-step consistency: w_1 + w_0 + w_1 = 1 (one macro step
        evolves dt total time)."""
        assert YOSHIDA_W1 + YOSHIDA_W0 + YOSHIDA_W1 == pytest.approx(1.0, abs=1e-12)

    def test_w0_is_negative(self):
        """Yoshida 1990: w_0 ≈ −1.7024 — negative middle weight is
        what allows the leading error term to cancel."""
        assert YOSHIDA_W0 < 0

    def test_w1_positive(self):
        assert YOSHIDA_W1 > 0

    def test_truth_label_and_guard(self):
        assert YO_TRUTH_LABEL == "SIFTA_YOSHIDA_SPLITTING_V1"
        assert "YOSHIDA_HIGH_ORDER_SPLITTING" in YOSHIDA_TRUTH_GUARD


class TestYoshidaAnchors:
    @pytest.mark.parametrize("anchor", YO_ANCHORS)
    def test_anchor_has_guards(self, anchor: YoshidaAnchor):
        assert anchor.supports.strip()
        assert anchor.does_not_support.strip()
        if anchor.doi:
            assert anchor.doi.startswith("10.")

    @pytest.mark.parametrize(
        "anchor_id",
        [
            "yoshida_1990_higher_order_symplectic",
            "suzuki_1991_general_theory_fractal_decompositions",
            "mclachlan_1995_high_order_splittings",
            "bao_jin_markowich_2003_numerical_schrodinger",
            "sportisse_2000_negative_step_splittings",
        ],
    )
    def test_required_anchor_present(self, anchor_id):
        assert anchor_id in yo_anchor_ids()


class TestYoshidaIntegrator:
    """The 4th-order Yoshida composition (Yoshida 1990) inherits SSF's
    unconditional stability and L² conservation (Bao-Jin-Markowich
    2003) and improves time accuracy from O(dt^2) to O(dt^4).
    """

    def test_l2_norm_conserved_better_than_machine_epsilon_floor(self):
        """Each SSF substep is unitary; the composition is also
        unitary. Norm drift per Yoshida macro step should remain at
        floating-point precision (Bao-Jin-Markowich 2003)."""
        cfg = SSFConfig(shape=(64, 32), dt=0.05, mass=1.0)
        yo = YoshidaSSF(cfg)
        yo.add_wave_packet(
            position=(32, 16), sigma=3.0, momentum=(0.3, 0.0),
        )
        yo.normalize()
        N0 = yo.norm_squared()
        yo.run(50)
        N50 = yo.norm_squared()
        assert abs(N50 - N0) < 1e-9, (
            f"Yoshida should preserve norm; |ΔN|={abs(N50 - N0):.2e}"
        )

    def test_yoshida_4th_order_more_accurate_than_strang_2nd_order(self):
        """Yoshida 1990 equation (4.6): a 4th-order method should
        converge faster as dt → 0 than a 2nd-order method.

        We compare both against a reference solution obtained with a
        very small SSF step. The Yoshida error should be smaller than
        the bare-SSF error at the same macro-step dt (or equal up to
        floating-point precision on small problems).
        """
        # Reference: very fine SSF run.
        ref_cfg = SSFConfig(shape=(64, 32), dt=0.001)
        ref = SplitStepFourier(ref_cfg)
        ref.add_wave_packet(
            position=(20, 16), sigma=4.0, momentum=(0.4, 0.0),
        )
        ref.normalize()
        ref.run(1000)   # total time 1.0
        psi_ref = ref.psi.copy()

        # Coarse SSF at dt=0.05 (20 steps for total time 1.0).
        ssf_coarse = SplitStepFourier(SSFConfig(shape=(64, 32), dt=0.05))
        ssf_coarse.add_wave_packet(
            position=(20, 16), sigma=4.0, momentum=(0.4, 0.0),
        )
        ssf_coarse.normalize()
        ssf_coarse.run(20)
        err_ssf = float(np.linalg.norm(ssf_coarse.psi - psi_ref))

        # Coarse Yoshida at dt=0.05 (20 macro steps for total time 1.0).
        yo_coarse = YoshidaSSF(SSFConfig(shape=(64, 32), dt=0.05))
        yo_coarse.add_wave_packet(
            position=(20, 16), sigma=4.0, momentum=(0.4, 0.0),
        )
        yo_coarse.normalize()
        yo_coarse.run(20)
        err_yo = float(np.linalg.norm(yo_coarse.psi - psi_ref))

        # Yoshida should be more accurate (smaller residual) or at
        # least competitive on this smooth problem.
        assert err_yo < err_ssf, (
            f"Yoshida 4th-order should beat SSF 2nd-order at dt=0.05; "
            f"err_yo={err_yo:.3e}, err_ssf={err_ssf:.3e}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# Bose-Hubbard
# ═══════════════════════════════════════════════════════════════════════════
class TestBoseHubbardAnchors:
    """Eight peer-reviewed cold-atom Bose-Hubbard anchors."""

    def test_truth_label_and_guard(self):
        assert BH_TRUTH_LABEL == "SIFTA_BOSE_HUBBARD_V1"
        assert "BOSE_HUBBARD_ANALOGUE_ONLY" in BOSE_HUBBARD_TRUTH_GUARD

    @pytest.mark.parametrize("anchor", BH_ANCHORS)
    def test_anchor_has_guards(self, anchor: BoseHubbardAnchor):
        assert anchor.supports.strip()
        assert anchor.does_not_support.strip()
        assert anchor.doi.startswith("10.")

    @pytest.mark.parametrize(
        "anchor_id",
        [
            "fisher_weichman_grinstein_fisher_1989",
            "jaksch_zoller_1998_bose_hubbard_optical_lattice",
            "greiner_2002_mott_insulator_quantum_phase_transition",
            "sachdev_1999_quantum_phase_transitions",
            "kuhner_monien_1998_phases_one_dimensional_bose_hubbard",
            "capogrosso_sansone_2007_qmc_bose_hubbard_3d",
            "bakr_2010_site_resolved_imaging",
            "endres_2012_higgs_amplitude_mode",
        ],
    )
    def test_required_anchor_present(self, anchor_id):
        assert anchor_id in bh_anchor_ids()


class TestBoseHubbardGroundState:
    """Fisher-Weichman-Grinstein-Fisher 1989 (PRB 40, 546) and
    Sachdev 1999: at integer filling and large U/J the ground state
    is the Mott insulator with n_i = N/M and zero number variance;
    at small U/J the ground state is the superfluid with broad number
    distribution.
    """

    def test_mott_limit_pins_occupation_to_filling(self):
        """At U/J = 100 with N=M (unit filling), every site has
        exactly 1 boson and number variance vanishes (Sachdev 1999
        Chapter 9).
        """
        cfg = BoseHubbardConfig(M=3, N=3, J=1.0, U=100.0, n_max=3)
        gs = compute_ground_state(cfg)
        for occ in gs.onsite_occupation:
            assert occ == pytest.approx(1.0, abs=0.05)
        assert gs.total_variance < 0.2

    def test_superfluid_limit_has_large_variance(self):
        """At U/J → 0 the system is essentially free bosons; the
        ground state delocalizes and the on-site number variance is
        large compared to the Mott limit (Fisher 1989 §IV).
        """
        cfg = BoseHubbardConfig(M=3, N=3, J=1.0, U=0.01, n_max=3)
        gs = compute_ground_state(cfg)
        assert gs.total_variance > 1.0

    def test_two_site_dimer_exact_values(self):
        """For the two-site Bose-Hubbard with N=2 at U=0, the ground
        state is the symmetric (b†_0 + b†_1)²/√(8) |vac⟩. The
        nearest-neighbour coherence ⟨b†_0 b_1⟩ = 1 in that case
        (Sachdev 1999 §9.1 — symmetric two-site limit).
        """
        cfg = BoseHubbardConfig(M=2, N=2, J=1.0, U=0.0, n_max=2)
        gs = compute_ground_state(cfg)
        assert gs.coherence_first_neighbor == pytest.approx(1.0, abs=0.05)
        # By symmetry each site has ⟨n_i⟩ = 1 at half filling N/M=1.
        assert gs.onsite_occupation[0] == pytest.approx(1.0, abs=1e-9)
        assert gs.onsite_occupation[1] == pytest.approx(1.0, abs=1e-9)

    def test_superfluid_to_mott_scan_is_monotonic(self):
        """Greiner 2002 (Nature 415, 39): increasing U/J drives the
        system from superfluid (large variance) toward Mott (zero
        variance). Our small-system ED should show monotonic decrease
        of total_variance with U/J.
        """
        scan = superfluid_mott_scan(
            M=3, N=3, J=1.0,
            U_over_J_values=[0.1, 1.0, 10.0, 100.0],
            n_max=3,
        )
        variances = [r["total_variance"] for r in scan["scan"]]
        # Each successive variance must not exceed the previous.
        for a, b in zip(variances, variances[1:]):
            assert b <= a + 1e-9, (
                f"variance should decrease with U/J; got {variances}"
            )
        # The endpoints must differ significantly.
        assert variances[0] > variances[-1] * 5

    def test_render_scan_ascii_well_formed(self):
        scan = superfluid_mott_scan(M=2, N=2, J=1.0,
                                    U_over_J_values=[0.1, 1.0, 10.0])
        text = render_scan_ascii(scan)
        assert "Bose-Hubbard" in text
        assert "U/J" in text


class TestBoseHubbardValidation:
    def test_requires_at_least_two_sites(self):
        with pytest.raises(ValueError):
            BoseHubbardConfig(M=1, N=1)

    def test_nmax_must_cover_filling(self):
        with pytest.raises(ValueError):
            BoseHubbardConfig(M=3, N=5, n_max=2)

    def test_basis_size_matches_expected(self):
        """For M=3, N=2 with n_max ≥ N, the canonical Fock basis has
        C(2 + 3 - 1, 2) = 6 states (Sachdev 1999 §9 basis counting)."""
        cfg = BoseHubbardConfig(M=3, N=2, n_max=2)
        gs = compute_ground_state(cfg)
        assert len(gs.state_vector) == 6
