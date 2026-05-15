#!/usr/bin/env python3
"""swarm_attachment_dynamics.py — §21 Vector #9: bond formation.

Architect framing (2026-05-13 close):
    "Not reproduction — emotional regulation, pair formation, motivation,
    signaling, trust. Agents that synchronize repeatedly become harder to
    separate; cooperative pairs stabilize each other; trusted agents
    reduce perturbation cost; long-term interaction changes field geometry."

This module implements that on top of the existing
AdaptivePolicySwarm machinery without modifying it. The new class
`AttachmentDynamicsSwarm` subclasses AdaptivePolicySwarm and adds:

  - **A**: pairwise affinity matrix (n × n). A[i,j] = A[j,i] grows when
    agents i and j are in nearby cells AND choose the same dominant
    behavior. Decays exponentially with `affinity_decay` each step.

  - **Momentum sharing (V2 default)**: bonded pairs partially
    AVERAGE their velocities each step. A perturbation kick on
    agent i is diluted on the next tick across i's bonded partners,
    who weren't kicked the same way. The dyad's centre-of-mass
    velocity moves less than a singleton's would. Share factor:
    `momentum_share_fraction * tanh(total_bond / saturation)`,
    bounded so no agent loses its identity.

  - **Bonded mass burden**: each agent's effective mass is
    INCREASED by a small term proportional to its total bond
    strength sum_j A[i,j]. Persistent dyads carry summed inertia
    and respond less to perturbation. (V1 had this inverted — mass
    RELIEF — which made bonded agents lighter and thus MORE
    responsive to perturbation noise. Honest correction in V2.)

  - **Asymmetric perturbation absorption**: the combination of
    momentum sharing + mass burden means bonded pairs absorb a
    velocity kick more cheaply than unbonded baseline. The kick's
    energy is averaged across the pair AND damped by extra inertia.

  - **Field-geometry receipt**: bonded clusters leave a higher local
    write density because each pair's deposits superpose. The receipt
    records this as "field geometry shift under bond formation."

Truth class: HYPOTHESIS — the headline finding (bonded dyads recover
faster from perturbation) needs to be reproduced across seeds. Receipt
is sha256-signed regardless of which direction the data goes.

Not romantic. Not reproductive. Just the engineering analogue of
"persistent cooperative pairs become computationally inseparable over
time."
"""
from __future__ import annotations

import hashlib
import json
import math
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

TRUTH_LABEL = "ATTACHMENT_DYNAMICS_V2"
LEDGER_NAME = "attachment_dynamics_receipts.jsonl"
TRUTH_BOUNDARY = (
    "Classical pairwise-affinity analogue on top of the Persistence "
    "Inertia Field. Bonds are scalar entries in a numpy matrix; no "
    "claim about consciousness, emotion, or biological pair-bonding."
)

# ── V2 design note ────────────────────────────────────────────────────
# V1 used (a) bond-pull positional force + (b) bond-mass relief. Honest
# negative result: ttr_bonded=201 > ttr_control=152, ratio 1.32. Wrong
# polarity — the pull added kinetic energy AFTER a perturbation kicked
# the pair apart (each agent accelerated toward the other's new
# off-axis position), and mass relief made bonded agents LIGHTER, i.e.
# more responsive to the perturbation noise. Both pushed against
# recovery instead of for it.
#
# V2 (this file): momentum sharing + bond-mass burden.
#   - bond_mechanism="momentum_share" (default): bonded pairs partially
#     average their velocities each step. A perturbation kick on agent i
#     gets diluted across its bond partners on the next tick — the
#     dyad's centre-of-mass velocity changes less than a singleton's
#     would, because the kick is averaged with bonded partners that
#     weren't kicked as hard.
#   - bond_mass_relief sign INVERTED: bonded agents become HEAVIER, not
#     lighter (persistent dyad has summed inertia). New name:
#     bond_mass_burden. Higher mass damps response to perturbation.
#   - "pull" mechanism kept as an opt-in for ablation comparison.
# ──────────────────────────────────────────────────────────────────────

try:
    import numpy as _np
    _HAS_NUMPY = True
except Exception:
    _HAS_NUMPY = False


class AttachmentDynamicsSwarm:
    """AdaptivePolicySwarm with pairwise affinity bonds.

    Wraps (does not inherit from) AdaptivePolicySwarm so the existing
    class stays untouched. The bond-aware step() delegates the physics
    to the underlying swarm and adds the affinity matrix updates +
    bond-force coupling + mass relief.
    """

    def __init__(
        self,
        n: int = 30,
        field_shape: tuple[int, int] = (24, 16),
        *,
        seed: int = 113,
        coupling: float = 1.0,
        learning_rate: float = 0.06,
        write_inertia_coefficient: float = 0.1,
        write_inertia_kind: str = "linear",
        # Attachment-specific knobs
        affinity_growth: float = 0.04,    # per matching-step bond gain
        affinity_decay: float = 0.005,    # per-step decay
        affinity_saturation: float = 4.0,  # tanh saturation point
        bond_mechanism: str = "momentum_share",  # "momentum_share" | "pull"
        momentum_share_fraction: float = 0.18,  # per-step velocity averaging weight
        bond_pull_strength: float = 0.0,  # legacy positional pull (off by default)
        bond_mass_burden: float = 0.25,    # mass INCREASE per unit bond (V2: heavier, not lighter)
        cell_neighborhood: int = 2,        # cells distance for "near"
    ) -> None:
        if not _HAS_NUMPY:
            raise RuntimeError("AttachmentDynamicsSwarm requires numpy")
        # Build the underlying adaptive swarm — same constructor surface
        # so the existing experiment scaffolds work unchanged.
        from System.swarm_higgs_stigmergy_field import AdaptivePolicySwarm
        self._swarm = AdaptivePolicySwarm(
            n=n, field_shape=field_shape, seed=seed,
            coupling=coupling, learning_rate=learning_rate,
            write_inertia_coefficient=write_inertia_coefficient,
            write_inertia_kind=write_inertia_kind,
        )
        self._n = n
        self._h, self._w = field_shape
        self._affinity_growth = float(affinity_growth)
        self._affinity_decay = float(affinity_decay)
        self._affinity_saturation = float(affinity_saturation)
        self._bond_mechanism = str(bond_mechanism)
        if self._bond_mechanism not in ("momentum_share", "pull", "none"):
            raise ValueError(
                f"bond_mechanism must be one of momentum_share/pull/none, "
                f"got {bond_mechanism!r}"
            )
        self._momentum_share_fraction = float(momentum_share_fraction)
        self._bond_pull_strength = float(bond_pull_strength)
        self._bond_mass_burden = float(bond_mass_burden)
        self._cell_neighborhood = int(cell_neighborhood)
        # Affinity matrix — symmetric, zero diagonal.
        self.affinity = _np.zeros((n, n), dtype=float)
        self._steps = 0
        # Snapshot of base mass so we can re-apply burden cleanly each
        # tick without unbounded ratcheting.
        self._base_mass = self._swarm.mass.copy()

    # Expose underlying swarm state read-only for downstream callers.
    @property
    def pos(self):
        return self._swarm.pos

    @property
    def vel(self):
        return self._swarm.vel

    @property
    def mass(self):
        return self._swarm.mass

    @property
    def n(self) -> int:
        return self._n

    def policy_entropy(self) -> float:
        return self._swarm.policy_entropy()

    def role_counts(self) -> dict[str, int]:
        return self._swarm.role_counts()

    def dominant_behavior_index(self):
        return self._swarm.dominant_behavior_index()

    # ── Bond-aware step ────────────────────────────────────────────
    def step(self, phi_array, dt: float = 0.05) -> None:
        """Advance the underlying swarm, then update affinities, then
        apply bond-force coupling + mass relief."""
        # Snapshot dominant behaviors BEFORE the swarm step (because
        # bonds form on the basis of synchronized choice at this tick).
        pre_dominant = self._swarm.dominant_behavior_index()
        pre_ix = (_np.floor(self._swarm.pos[:, 0]).astype(int)) % self._w
        pre_iy = (_np.floor(self._swarm.pos[:, 1]).astype(int)) % self._h

        # Advance the underlying adaptive swarm one step.
        self._swarm.step(phi_array, dt=dt)

        # ── Affinity update ─────────────────────────────────────
        # Two agents grow their bond if (1) they are in cells within
        # cell_neighborhood AND (2) they share dominant behavior.
        # Vectorised pairwise check.
        h_dist = _np.minimum(
            _np.abs(pre_ix[:, None] - pre_ix[None, :]),
            self._w - _np.abs(pre_ix[:, None] - pre_ix[None, :]),
        )
        v_dist = _np.minimum(
            _np.abs(pre_iy[:, None] - pre_iy[None, :]),
            self._h - _np.abs(pre_iy[:, None] - pre_iy[None, :]),
        )
        near = (h_dist <= self._cell_neighborhood) & (v_dist <= self._cell_neighborhood)
        same_role = pre_dominant[:, None] == pre_dominant[None, :]
        bond_event = near & same_role
        _np.fill_diagonal(bond_event, False)
        self.affinity = self.affinity + self._affinity_growth * bond_event.astype(float)
        # Exponential decay
        self.affinity = self.affinity * (1.0 - self._affinity_decay)
        self.affinity = _np.maximum(self.affinity, 0.0)
        # Symmetric guard
        self.affinity = 0.5 * (self.affinity + self.affinity.T)

        # ── V2: Momentum sharing (default) ─────────────────────
        # Bonded pairs partially average their velocities each step.
        # This DAMPS the response to perturbation: when agent i gets
        # kicked, on the next tick a fraction of its velocity is
        # replaced by the bond-weighted mean of its partners. The kick
        # is diluted across the dyad. Singletons keep their full kick.
        #
        # Implementation: v_i_new = (1 - share_i) * v_i + share_i * v_bar_i
        # where v_bar_i = sum_j w_ij * v_j / sum_j w_ij
        # and share_i = momentum_share_fraction * tanh(total_bond_i / sat)
        #
        # tanh saturation means weak bonds barely share; strong bonds
        # average heavily. The share factor stays bounded by
        # momentum_share_fraction so no agent loses its identity.
        if self._bond_mechanism == "momentum_share" and self.affinity.max() > 1e-6:
            weights = _np.tanh(self.affinity / self._affinity_saturation)
            # Zero diagonal so an agent doesn't "average with itself"
            _np.fill_diagonal(weights, 0.0)
            row_sum = weights.sum(axis=1)  # (n,)
            has_partners = row_sum > 1e-6
            if has_partners.any():
                # Weighted mean velocity from each agent's bonded partners
                # v_bar[i] = sum_j weights[i,j] * vel[j] / row_sum[i]
                weighted_partner_vel = weights @ self._swarm.vel  # (n, d)
                v_bar = _np.zeros_like(self._swarm.vel)
                v_bar[has_partners] = (
                    weighted_partner_vel[has_partners]
                    / row_sum[has_partners, None]
                )
                # Share factor per agent — bounded in [0, momentum_share_fraction]
                share = self._momentum_share_fraction * _np.tanh(
                    row_sum / self._affinity_saturation
                )
                share[~has_partners] = 0.0
                # Blend
                self._swarm.vel = (
                    (1.0 - share[:, None]) * self._swarm.vel
                    + share[:, None] * v_bar
                )
        elif self._bond_mechanism == "pull" and self.affinity.max() > 1e-6:
            # Legacy V1 mechanism kept for ablation.
            weights = _np.tanh(self.affinity / self._affinity_saturation)
            diff = self._swarm.pos[None, :, :] - self._swarm.pos[:, None, :]
            diff[..., 0] = ((diff[..., 0] + self._w / 2) % self._w) - self._w / 2
            diff[..., 1] = ((diff[..., 1] + self._h / 2) % self._h) - self._h / 2
            pull = _np.einsum("ij,ijd->id", weights, diff) * self._bond_pull_strength
            inv_mass = 1.0 / self._swarm.mass
            self._swarm.vel = self._swarm.vel + pull * inv_mass[:, None] * dt

        # ── V2: Bond mass BURDEN (inverted from V1 relief) ────
        # Persistent dyads carry SUMMED inertia. Each agent's effective
        # mass is INCREASED by burden * tanh(sum bonds / saturation).
        # Higher mass damps response to perturbation — the architectural
        # claim "trusted agents reduce perturbation cost" expressed as
        # heavier inertia, not lighter responsiveness.
        # Reset to base each tick to avoid unbounded ratcheting; the
        # burden is a function of current bond strength only.
        if self._bond_mass_burden > 0.0 and self.affinity.max() > 1e-6:
            row_bond_strength = self.affinity.sum(axis=1)
            burden = self._bond_mass_burden * _np.tanh(
                row_bond_strength / self._affinity_saturation
            )
            self._swarm.mass = self._base_mass + burden
        else:
            self._swarm.mass = self._base_mass.copy()

        self._steps += 1

    # ── Bond statistics ─────────────────────────────────────────
    def bond_statistics(self) -> dict[str, Any]:
        """Receipt-friendly summary of the current bond network."""
        n = self._n
        # Number of pairs whose affinity exceeds a small threshold
        threshold = 0.5
        upper = _np.triu(self.affinity, k=1)
        bonded_pairs = int((upper > threshold).sum())
        max_bond = float(upper.max()) if upper.size > 0 else 0.0
        mean_bond = float(upper[upper > 0].mean()) if (upper > 0).any() else 0.0
        # Top-3 bonded pairs (i, j, strength)
        pairs = []
        if bonded_pairs > 0:
            ii, jj = _np.unravel_index(_np.argsort(-upper, axis=None), upper.shape)
            for k in range(min(3, bonded_pairs)):
                i, j = int(ii[k]), int(jj[k])
                pairs.append({"i": i, "j": j, "strength": round(float(upper[i, j]), 4)})
        # Distribution of bond-strength row sums
        row_sums = self.affinity.sum(axis=1)
        return {
            "n_agents": n,
            "n_bonded_pairs_above_0_5": bonded_pairs,
            "max_pairwise_bond": round(max_bond, 4),
            "mean_nonzero_bond": round(mean_bond, 4),
            "top_bonded_pairs": pairs,
            "max_row_bond_sum": round(float(row_sums.max()), 4),
            "mean_row_bond_sum": round(float(row_sums.mean()), 4),
        }

    def apply_perturbation(self, amplitude: float = 2.0, seed: int = 0) -> None:
        """Inject a velocity perturbation across the swarm — used to
        compare bonded vs unbonded recovery."""
        rng = _np.random.default_rng(seed if seed else int(time.time()))
        kick = rng.normal(scale=amplitude, size=self._swarm.vel.shape)
        self._swarm.vel = self._swarm.vel + kick

    def mean_speed(self) -> float:
        return float(_np.mean(_np.linalg.norm(self._swarm.vel, axis=1)))


def run_attachment_experiment(
    *,
    n_agents: int = 40,
    field_shape: tuple[int, int] = (24, 16),
    relax_steps: int = 180,
    bond_steps: int = 600,
    perturbation_amplitude: float = 3.0,
    recovery_steps: int = 200,
    coupling: float = 1.0,
    learning_rate: float = 0.06,
    write_inertia_coefficient: float = 0.1,
    write_inertia_kind: str = "linear",
    seed: int = 113,
    state_root: str | Path | None = None,
    write: bool = True,
) -> dict[str, Any]:
    """Three-phase experiment:
       1. Let bonds form (`bond_steps` of normal evolution).
       2. Apply a velocity perturbation.
       3. Run `recovery_steps` and measure how fast mean speed returns
          to baseline.

    Compare against a control swarm that runs the same phases without
    bond formation (zeroed affinity). The bonded swarm should recover
    faster — that's the headline test. Honest reporting either way.
    """
    if not _HAS_NUMPY:
        raise RuntimeError("run_attachment_experiment requires numpy")
    from System.swarm_higgs_stigmergy_field import (
        HiggsFieldConfig, HiggsStigmergyField, phi_as_array,
    )

    h, w = field_shape
    cfg = HiggsFieldConfig(seed=seed, width=w, height=h)

    def _build_swarm(zero_bonds: bool):
        field = HiggsStigmergyField(cfg)
        field.relax(relax_steps)
        swarm = AttachmentDynamicsSwarm(
            n=n_agents, field_shape=field_shape, seed=seed,
            coupling=coupling, learning_rate=learning_rate,
            write_inertia_coefficient=write_inertia_coefficient,
            write_inertia_kind=write_inertia_kind,
        )
        if zero_bonds:
            # Disable affinity growth, mass burden, and bond mechanism
            # so the swarm behaves like the baseline AdaptivePolicySwarm.
            swarm._affinity_growth = 0.0
            swarm._bond_pull_strength = 0.0
            swarm._bond_mass_burden = 0.0
            swarm._momentum_share_fraction = 0.0
            swarm._bond_mechanism = "none"
        return field, swarm

    # Phase A: bonded run
    field_a, bonded = _build_swarm(zero_bonds=False)
    for _ in range(bond_steps):
        field_a.step()
        bonded.step(phi_as_array(field_a))
    pre_perturb_speed_bonded = bonded.mean_speed()
    bond_stats = bonded.bond_statistics()
    bonded.apply_perturbation(amplitude=perturbation_amplitude, seed=seed * 7)
    post_perturb_speed_bonded = bonded.mean_speed()
    recovery_curve_bonded = []
    for _ in range(recovery_steps):
        field_a.step()
        bonded.step(phi_as_array(field_a))
        recovery_curve_bonded.append(bonded.mean_speed())

    # Phase B: control run (no bonds)
    field_b, control = _build_swarm(zero_bonds=True)
    for _ in range(bond_steps):
        field_b.step()
        control.step(phi_as_array(field_b))
    pre_perturb_speed_ctrl = control.mean_speed()
    control.apply_perturbation(amplitude=perturbation_amplitude, seed=seed * 7)
    post_perturb_speed_ctrl = control.mean_speed()
    recovery_curve_ctrl = []
    for _ in range(recovery_steps):
        field_b.step()
        control.step(phi_as_array(field_b))
        recovery_curve_ctrl.append(control.mean_speed())

    # Recovery metric: how many steps until mean speed returns within
    # 20% of pre-perturbation baseline? Lower = faster recovery.
    def _ttr(curve: list[float], baseline: float) -> int:
        target = baseline * 1.20
        for i, v in enumerate(curve):
            if v <= target:
                return i + 1
        return len(curve) + 1  # didn't recover within window

    ttr_bonded = _ttr(recovery_curve_bonded, pre_perturb_speed_bonded)
    ttr_ctrl = _ttr(recovery_curve_ctrl, pre_perturb_speed_ctrl)

    bonded_recovers_faster = ttr_bonded < ttr_ctrl

    result = {
        "truth_label": TRUTH_LABEL,
        "truth_class": "HYPOTHESIS",
        "truth_boundary": TRUTH_BOUNDARY,
        "simulated": True,
        "no_biology_claim": True,
        "research_question_answered": (
            "§21 Vector #9 — do persistent cooperative pairs become "
            "computationally inseparable over time, and do bonded "
            "pairs recover faster from perturbation than unbonded "
            "baselines?"
        ),
        "config": {
            "n_agents": n_agents, "bond_steps": bond_steps,
            "recovery_steps": recovery_steps,
            "perturbation_amplitude": perturbation_amplitude,
            "field_shape": list(field_shape), "seed": seed,
        },
        "bond_phase": {
            "bond_statistics": bond_stats,
            "pre_perturb_mean_speed_bonded": round(pre_perturb_speed_bonded, 4),
            "post_perturb_mean_speed_bonded": round(post_perturb_speed_bonded, 4),
        },
        "control_phase": {
            "pre_perturb_mean_speed_control": round(pre_perturb_speed_ctrl, 4),
            "post_perturb_mean_speed_control": round(post_perturb_speed_ctrl, 4),
        },
        "recovery_measurement": {
            "ttr_bonded_steps": ttr_bonded,
            "ttr_control_steps": ttr_ctrl,
            "bonded_recovers_faster": bonded_recovers_faster,
            "ttr_ratio_bonded_over_control": round(ttr_bonded / max(ttr_ctrl, 1), 4),
        },
        "mechanism": "momentum_share + mass_burden (V2)",
        "v1_history_note": (
            "V1 used bond_pull positional force + mass_relief and "
            "produced ttr_bonded > ttr_control (ratio 1.32). Wrong "
            "polarity: pull added kinetic energy after perturbation, "
            "relief made bonded agents lighter (more responsive to "
            "noise). V2 inverts both: momentum sharing damps the kick "
            "across the dyad, mass burden increases inertia."
        ),
        "interpretation": (
            "If bonded_recovers_faster is True, persistent dyads "
            "absorbed the perturbation more cheaply than independent "
            "agents — attachment reduced perturbation cost. If False, "
            "the share fraction may be too weak vs perturbation "
            "amplitude, or bonds didn't have time to form (try larger "
            "momentum_share_fraction, larger bond_mass_burden, or "
            "longer bond_steps). Honest reporting either way."
        ),
    }
    if write:
        write_attachment_receipt(result, state_root=state_root)
    return result


def write_attachment_receipt(
    result: dict[str, Any], *, state_root: str | Path | None = None,
) -> dict[str, Any]:
    state = Path(state_root) if state_root else _STATE
    state.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(result, sort_keys=True, separators=(",", ":"))
    row = {
        "ts": time.time(),
        "kind": "ATTACHMENT_DYNAMICS_EXPERIMENT",
        "trace_id": str(uuid.uuid4()),
        "truth_label": TRUTH_LABEL,
        "truth_class": "HYPOTHESIS",
        "truth_boundary": TRUTH_BOUNDARY,
        "sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        "payload": result,
    }
    with (state / LEDGER_NAME).open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")
    return row


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--n", type=int, default=40)
    p.add_argument("--bond-steps", type=int, default=600)
    p.add_argument("--recovery-steps", type=int, default=200)
    p.add_argument("--amplitude", type=float, default=3.0)
    p.add_argument("--no-write", action="store_true")
    args = p.parse_args()
    r = run_attachment_experiment(
        n_agents=args.n,
        bond_steps=args.bond_steps,
        recovery_steps=args.recovery_steps,
        perturbation_amplitude=args.amplitude,
        write=not args.no_write,
    )
    print(json.dumps(r, indent=2, default=str))
