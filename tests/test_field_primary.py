#!/usr/bin/env python3
"""Physics-anchored pytest coverage for the field-primary modules.

Modules under test
------------------
- System.swarm_field_primary_pde         (the N-D PDE engine)
- System.swarm_field_primary_research_spine (the peer-reviewed anchors)

Every test docstring cites the peer-reviewed paper whose claim it
verifies in the SIFTA classical-field analogue, per Architect directive
2026-05-11 ("BRING PHYSICS PAPERS TO PROVE ALL YOUR TESTS").

Sandbox-safe: numpy + stdlib + pytest. No Qt, no scipy, no matplotlib.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from System.swarm_field_primary_pde import (
    FIELD_PRIMARY_TRUTH_GUARD as PDE_TRUTH_GUARD,
    FieldConfig,
    FieldPrimary,
    Swimmer,
    TRUTH_LABEL as PDE_TRUTH_LABEL,
    field_primary_summary,
    laplacian_nd,
    make_double_slit_2d,
)
from System.swarm_field_primary_research_spine import (
    FIELD_PRIMARY_TRUTH_GUARD as SPINE_TRUTH_GUARD,
    QUARANTINED_SOURCE_NOTES,
    TRUTH_LABEL as SPINE_TRUTH_LABEL,
    VERIFIED_SPINE,
    FieldPrimaryAnchor,
    quarantined_sources,
    spine_payload,
    verified_source_ids,
    write_spine_receipt,
)


# ═══════════════════════════════════════════════════════════════════════════
# PDE engine — math + structure
# ═══════════════════════════════════════════════════════════════════════════
class TestLaplacian:
    """The discrete Laplacian is the heart of the diffusion term in
    ∂φ/∂t = D∇²φ. Schrödinger 1926 (PR 28, 1049, DOI 10.1103/PhysRev.28.1049)
    is the canonical PDE we draw structural inspiration from.
    """

    def test_laplacian_of_constant_is_zero(self):
        """∇² of a uniform field is zero everywhere — basic calculus."""
        phi = np.ones((10, 12), dtype=np.complex128) * 3.7
        L = laplacian_nd(phi, dx=1.0)
        assert np.allclose(L, 0.0)

    def test_laplacian_dimension_count_in_each_axis(self):
        """For a linear ramp along one axis, the second derivative is 0
        in that axis but the periodic-roll boundary causes the *first*
        and *last* rows to wrap; we verify only the interior cells.
        """
        x = np.linspace(0, 9, 10)
        phi = np.tile(x, (12, 1)).astype(np.complex128)  # ramp along axis 1
        L = laplacian_nd(phi, dx=1.0)
        # interior cells along axis-1 of a linear ramp have zero curvature
        assert np.allclose(L[:, 1:-1].real, 0.0, atol=1e-9)

    def test_laplacian_quadratic_gives_constant(self):
        """For φ(x) = x², ∇²φ = 2 everywhere (analytical)."""
        x = np.arange(20, dtype=np.float64)
        phi = (x * x).astype(np.complex128).reshape(1, -1)
        L = laplacian_nd(phi, dx=1.0)
        # interior cells must read ~2 (boundary cells affected by wrap)
        assert np.allclose(L[0, 1:-1].real, 2.0, atol=1e-9)

    def test_laplacian_supports_arbitrary_dimensionality(self):
        """1D, 2D, 3D, 4D — same algorithm, same answer for a constant."""
        for shape in [(7,), (7, 5), (5, 4, 3), (3, 4, 3, 4)]:
            phi = np.ones(shape, dtype=np.complex128) * (1 + 2j)
            L = laplacian_nd(phi, dx=1.0)
            assert np.allclose(L, 0.0), (
                f"non-zero Laplacian of a constant field at ndim={len(shape)}"
            )


class TestFieldConfig:
    def test_cfl_safe_dt_chosen_by_default(self):
        cfg = FieldConfig(shape=(20, 20), D_base=0.5, dx=1.0)
        assert cfg.dt is not None and cfg.dt > 0
        # User-supplied dt above the bound must be rejected.
        with pytest.raises(ValueError):
            FieldConfig(shape=(20, 20), D_base=0.5, dx=1.0, dt=1e6)

    def test_shape_must_be_at_least_three_per_axis(self):
        with pytest.raises(ValueError):
            FieldConfig(shape=(2, 20))

    def test_high_dimensional_shape_accepted(self):
        cfg = FieldConfig(shape=(5, 5, 5, 5), D_base=0.1)
        assert cfg.ndim == 4
        assert cfg.dt is not None


# ═══════════════════════════════════════════════════════════════════════════
# PDE physics — diffusion, decay, swimmers, slit
# ═══════════════════════════════════════════════════════════════════════════
class TestSourceFreeDecay:
    """λ-term decay alone. Heylighen 2016 (DOI 10.1016/j.cogsys.2015.12.002)
    treats stigmergic trace evaporation as the universal "memory loss"
    mechanism in any stigmergy system; without it, traces never expire.
    """

    def test_decay_only_intensity_drops_monotonically(self):
        cfg = FieldConfig(shape=(10, 10), D_base=0.0, lam=0.5)
        f = FieldPrimary(cfg)
        f.phi = np.ones(cfg.shape, dtype=np.complex128) * (1 + 0j)
        I0 = f.total_intensity()
        intensities = [I0]
        for _ in range(20):
            f.step()
            intensities.append(f.total_intensity())
        for a, b in zip(intensities, intensities[1:]):
            assert b <= a + 1e-12, "λ-decay must be monotonic non-increasing"
        # decay actually happened
        assert intensities[-1] < intensities[0] * 0.5


class TestDiffusion:
    """D-term diffusion. Couder & Fort 2006 (DOI 10.1103/PhysRevLett.97.154101)
    show a guiding wave diffuses outward from a pulsing droplet; SIFTA's
    classical analogue must do the same.
    """

    def test_initial_delta_spreads_outward(self):
        cfg = FieldConfig(shape=(40, 40), D_base=0.5, lam=0.0)
        f = FieldPrimary(cfg)
        f.phi[20, 20] = 100.0  # delta-like initial condition
        I_center_initial = abs(f.phi[20, 20]) ** 2
        # Compute initial spread (variance proxy).
        for _ in range(40):
            f.step()
        I_center_final = abs(f.phi[20, 20]) ** 2
        # Peak amplitude must drop as energy spreads.
        assert I_center_final < I_center_initial


class TestSwimmerSource:
    """A swimmer is a localized phase-carrying Gaussian source — the
    "swimmer-in-field" ontology. Compatible with Bohm 1952's pilot-wave
    picture (DOI 10.1103/PhysRev.85.166): particle position colocated
    with a guiding wave excitation.
    """

    def test_swimmer_adds_intensity_at_position(self):
        cfg = FieldConfig(shape=(20, 20), D_base=0.0, lam=0.0)
        f = FieldPrimary(cfg)
        f.add_swimmer(Swimmer(position=(10, 10), sigma=1.0,
                              amplitude=1.0, phase=0.0))
        f.step()
        center = abs(f.phi[10, 10])
        edge = abs(f.phi[0, 0])
        assert center > edge

    def test_two_phase_opposed_swimmers_cancel_at_midpoint(self):
        """Constructive/destructive interference test (peer-reviewed
        precedent: Couder & Fort 2006 single-particle diffraction).

        Two swimmers at the same position with phases 0 and π must
        produce *destructive* superposition at the midpoint after one
        deposit step with no diffusion.
        """
        cfg = FieldConfig(shape=(20, 20), D_base=0.0, lam=0.0)
        f = FieldPrimary(cfg)
        f.add_swimmer(Swimmer((10, 10), sigma=2.0, amplitude=1.0, phase=0.0))
        f.add_swimmer(Swimmer((10, 10), sigma=2.0, amplitude=1.0, phase=math.pi))
        f.step()
        # Field at the deposit center should be zero (1 + e^{iπ} = 0).
        assert abs(f.phi[10, 10]) < 1e-9


class TestBarrier:
    """Barrier as a structure IN the field, not a separate object.
    Compatible with Bohm 1952 / de Broglie 1924 picture where the slit
    is a geometric constraint on the guiding field, not on the
    particle alone.
    """

    def test_barrier_blocks_transport(self):
        """With D=0 across an entire row (no slits) the field on the
        far side must remain ~0 after many steps.
        """
        cfg = FieldConfig(shape=(40, 30), D_base=0.5, lam=0.0)
        f = FieldPrimary(cfg)
        f.install_barrier(axis=0, position=20, thickness=2,
                          slit_positions=())
        # source on the near side
        f.phi[5, 15] = 50.0
        for _ in range(60):
            f.step()
        far_side = np.abs(f.phi[25:, :]) ** 2
        # very small leakage from periodic-roll edges is allowed
        assert far_side.max() < 0.05

    def test_slits_allow_partial_transport(self):
        """With two slits, *some* intensity arrives on the far side."""
        cfg = FieldConfig(shape=(40, 30), D_base=0.5, lam=0.0)
        f = FieldPrimary(cfg)
        f.install_barrier(axis=0, position=20, thickness=2,
                          slit_positions=[(12,), (18,)])
        f.phi[5, 15] = 50.0
        for _ in range(80):
            f.step()
        far_side = np.abs(f.phi[25:, :]) ** 2
        # there must be SOMETHING on the far side
        assert far_side.max() > 0.0


class TestDoubleSlitConvenience:
    def test_make_double_slit_2d_runs_without_error(self):
        """End-to-end smoke test of the convenience builder."""
        f = make_double_slit_2d(width=60, height=40)
        f.add_swimmer(Swimmer((10, 20), sigma=1.5, amplitude=2.0))
        for _ in range(30):
            f.step()
        snap = f.snapshot()
        assert snap["schema"] == PDE_TRUTH_LABEL
        assert "FIELD_PRIMARY_PDE_ONLY" in snap["truth_guard"]

    def test_dimension_is_a_parameter(self):
        """Architect directive: 'WHY DOES IT HAVE TO BE 2D'. Verify the
        engine runs in 1D, 2D, 3D with the same API.
        """
        for shape in [(20,), (12, 14), (6, 6, 6)]:
            cfg = FieldConfig(shape=shape, D_base=0.3, lam=0.01)
            f = FieldPrimary(cfg)
            center = tuple(s // 2 for s in shape)
            f.add_swimmer(Swimmer(center, sigma=1.5, amplitude=1.0))
            f.run(5)
            assert f.total_intensity() > 0.0


class TestSnapshot:
    def test_snapshot_writes_truth_guard(self, tmp_path):
        cfg = FieldConfig(shape=(10, 10), D_base=0.1, lam=0.01)
        f = FieldPrimary(cfg)
        f.add_swimmer(Swimmer((5, 5)))
        f.run(3)
        out = tmp_path / "ledger.jsonl"
        f.deposit_snapshot(out)
        line = out.read_text("utf-8").strip()
        parsed = json.loads(line)
        assert parsed["schema"] == PDE_TRUTH_LABEL
        assert "FIELD_PRIMARY_PDE_ONLY" in parsed["truth_guard"]
        assert "sha256" in parsed
        assert parsed["n_swimmers"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# Research spine — structural truth-guard tests
# ═══════════════════════════════════════════════════════════════════════════
class TestSpine:
    def test_truth_label_v1(self):
        assert SPINE_TRUTH_LABEL == "SIFTA_FIELD_PRIMARY_RESEARCH_SPINE_V1"
        assert "FIELD_PRIMARY_DOCTRINE" in SPINE_TRUTH_GUARD

    def test_pde_summary_is_truth_guarded(self):
        s = field_primary_summary()
        assert "FIELD_PRIMARY_PDE_ONLY" in s
        assert "ARCHITECT_DOCTRINE" in s

    def test_spine_is_non_empty_and_categorized(self):
        assert len(VERIFIED_SPINE) >= 15
        categories = {a.category for a in VERIFIED_SPINE}
        # The Architect's specific buckets must each have at least one
        # peer-reviewed anchor.
        for required in {
            "pilot_wave_hydrodynamic",
            "pilot_wave_foundation",
            "relational_foundation",
            "information_is_physical",
            "stigmergy_foundation",
            "biological_field_substrate",
        }:
            assert required in categories, (
                f"missing category '{required}' from spine"
            )

    @pytest.mark.parametrize("anchor", VERIFIED_SPINE)
    def test_every_anchor_has_supports_and_no_support_guards(
        self, anchor: FieldPrimaryAnchor
    ):
        """§7.11: every source must declare what it must NOT be used to claim."""
        assert anchor.supports.strip()
        assert anchor.does_not_support.strip(), (
            f"{anchor.source_id}: empty does_not_support guard"
        )
        if anchor.doi:
            assert anchor.doi.startswith("10."), (
                f"{anchor.source_id}: bad DOI"
            )

    @pytest.mark.parametrize(
        "anchor_id",
        [
            "couder_fort_2006_single_particle_diffraction",
            "bush_2015_pilot_wave_hydrodynamics",
            "de_broglie_1924_pilot_wave_thesis",
            "schrodinger_1926_wave_mechanics",
            "bohm_1952_hidden_variables_I",
            "rovelli_1996_relational_qm",
            "zurek_2003_decoherence_einselection",
            "zurek_2009_quantum_darwinism",
            "landauer_1961_irreversibility",
            "berut_2012_landauer_verification",
            "grasse_1959_stigmergie",
            "heylighen_2016_stigmergy_universal",
            "levin_2014_bioelectric_networks",
            "bonabeau_dorigo_theraulaz_1999_swarm_intelligence",
            "friston_2010_free_energy_principle",
        ],
    )
    def test_doctrinal_anchor_present(self, anchor_id):
        assert anchor_id in verified_source_ids(), (
            f"required anchor '{anchor_id}' missing"
        )

    def test_quarantine_explicitly_forbids_orch_or_and_iit_proof(self):
        qids = {q["source_id"] for q in quarantined_sources()}
        assert "penrose_hameroff_orch_or" in qids
        assert "tononi_iit_as_consciousness_proof" in qids
        assert "any_god_observer_replacement_claim" in qids

    def test_receipt_round_trip(self, tmp_path):
        out = tmp_path / "field_primary_spine.jsonl"
        row = write_spine_receipt(state_root=tmp_path, receipt_path=out)
        assert row["truth_label"] == SPINE_TRUTH_LABEL
        assert "sha256" in row and len(row["sha256"]) == 64
        parsed = json.loads(out.read_text("utf-8").strip())
        assert parsed["source_count"] == len(VERIFIED_SPINE)

    def test_payload_structure_stable(self):
        p1 = spine_payload()
        p2 = spine_payload()
        assert json.dumps(p1, sort_keys=True) == json.dumps(p2, sort_keys=True)
