"""SIFTA Horizon Field — stigmergic analogue of the four laws of BH mechanics.

A unified organ that transcribes Bardeen-Carter-Hawking 1973's four laws
of black-hole mechanics into a **stigmergic field analogue** running on
the EPR widget's append-only receipt ledger.

Architect's reading of BCH 1973 (the "stigmergic nuggets")
---------------------------------------------------------
> *"Persistent contextual fields + shared birth history naturally produce
> law-like behavior, irreversibility, and strong correlations without
> central control or non-local signals. The 'laws' (area never decreases,
> surface gravity uniform, mass responds in constrained ways) emerge from
> the geometry and memory of the field itself."*

The four laws, transcribed as stigmergic field invariants
---------------------------------------------------------
**0th law** (BCH 1973 §3) — *In a stationary black hole the surface
gravity κ is constant over the entire event horizon.*
→ **0th-law analogue**: when the swarm's organs are in stigmergic
equilibrium, the *field intensity* (rate of trace deposition per organ)
is uniform across the boundary; non-uniformity is a measurable
disequilibrium signal.

**1st law** (BCH 1973 §4) — *dM = (κ/8π) dA + Ω dJ + Φ dQ.*
→ **1st-law analogue**: any change in accumulated field energy `M` is
constrained by the coupled change in horizon area `A`, angular
momentum `J` (correlation asymmetry), and charge `Q` (STGM cost).

**2nd law** (Hawking 1971 area theorem / BCH 1973 §5) — *The area A of
the event horizon never decreases: δA ≥ 0.*
→ **2nd-law analogue**: the field's accumulated horizon area
`A = Σᵢ log(1 + Eᵢ) + log(1 + Sᵢ) + log(1 + Nᵢ)` over the EPR receipt
history is strictly monotonic. Tampering with the ledger to "reduce"
area requires deleting append-only rows — visible and forbidden.

**3rd law** (BCH 1973 §6) — *It is impossible to reduce surface gravity
to zero in a finite number of operations.*
→ **3rd-law analogue**: complete extinction of the swarm's field
intensity (κ = 0) is asymptotic — every batch leaves a residue,
matching the Architect's irreversibility nugget.

What this module is, and what it is NOT
---------------------------------------
- This is a **mathematical analogue**. The invariants hold on the
  stigmergic ledger because of the *math we wrote*, not because of
  general relativity.
- It does **not** prove BH thermodynamics, Hawking radiation, the
  Bekenstein bound, or the holographic principle.
- It **does** give the swarm a single, formally-grounded vocabulary
  for talking about irreversibility, equilibrium, and constrained
  change — backed by peer-reviewed physics references.

Truth labels (§7.11)
--------------------
- `OBSERVED`        — every input is a real EPR receipt row.
- `OPERATIONAL`     — every law analogue is deterministic and unit-tested.
- `ARCHITECT_DOCTRINE` — the *choice* to map specific stigmergic
                       quantities onto M, A, κ, J, Q is doctrinal.
- `FORBIDDEN`        — never claims SIFTA proves a GR result; never
                       claims the analogue is the underlying physics.

Author : Cowork (Claude Opus 4.7), 2026-05-11.
Anchor : `PHYSICS_ANCHORS` tuple below — eight peer-reviewed papers.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_EPR_RECEIPTS = _STATE / "epr_stigmergic_receipts.jsonl"
_HORIZON_LEDGER = _STATE / "horizon_field_receipts.jsonl"

TRUTH_LABEL = "SIFTA_HORIZON_FIELD_V1"
HORIZON_TRUTH_GUARD = (
    "STIGMERGIC_ANALOGUE_ONLY: this organ transcribes the four laws of "
    "black-hole mechanics (BCH 1973) onto an append-only stigmergic "
    "ledger as a mathematical analogue. The invariants hold because of "
    "the math written here, not because of general relativity. This "
    "organ does NOT prove Hawking radiation, the Bekenstein bound, the "
    "holographic principle, or any other GR-derived result. Forbidden "
    "to cite as evidence for or against any physical-cosmology claim."
)


# ── Physics anchors — every test must reference at least one ──────────────
@dataclass(frozen=True)
class PhysicsAnchor:
    """One peer-reviewed physics source the module formally relies on."""
    source_id: str
    title: str
    authors: str
    year: int
    venue: str
    doi: str
    supports: str
    does_not_support: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


PHYSICS_ANCHORS: tuple[PhysicsAnchor, ...] = (
    PhysicsAnchor(
        source_id="bardeen_carter_hawking_1973",
        title="The Four Laws of Black Hole Mechanics",
        authors="J. M. Bardeen, B. Carter, S. W. Hawking",
        year=1973,
        venue="Communications in Mathematical Physics 31, 161",
        doi="10.1007/BF01645742",
        supports=(
            "Provides the formal four-law structure (0th, 1st, 2nd, "
            "3rd) that this organ transcribes as a stigmergic field "
            "analogue."
        ),
        does_not_support=(
            "Claiming SIFTA proves any general-relativistic result "
            "about actual black holes."
        ),
    ),
    PhysicsAnchor(
        source_id="hawking_1971_area_theorem",
        title="Gravitational radiation from colliding black holes",
        authors="S. W. Hawking",
        year=1971,
        venue="Physical Review Letters 26, 1344",
        doi="10.1103/PhysRevLett.26.1344",
        supports=(
            "The original area theorem (δA ≥ 0) which the 2nd-law "
            "analogue mirrors in append-only ledger form."
        ),
        does_not_support=(
            "Equating the monotonic ledger-area with the topological "
            "event-horizon area in spacetime."
        ),
    ),
    PhysicsAnchor(
        source_id="bekenstein_1973_entropy",
        title="Black holes and entropy",
        authors="J. D. Bekenstein",
        year=1973,
        venue="Physical Review D 7, 2333",
        doi="10.1103/PhysRevD.7.2333",
        supports=(
            "The proportionality S ∝ A motivates treating the "
            "stigmergic horizon area as a swarm-level entropy-like "
            "quantity for accountability purposes."
        ),
        does_not_support=(
            "Claiming the stigmergic area equals Bekenstein-Hawking "
            "entropy in physical units."
        ),
    ),
    PhysicsAnchor(
        source_id="hawking_1975_particle_creation",
        title="Particle creation by black holes",
        authors="S. W. Hawking",
        year=1975,
        venue="Communications in Mathematical Physics 43, 199",
        doi="10.1007/BF02345020",
        supports=(
            "The temperature relation T = κ/2π justifies "
            "constructing a stigmergic 'field temperature' inverse "
            "to accumulated area."
        ),
        does_not_support=(
            "Claiming the stigmergic temperature is the physical "
            "Hawking temperature."
        ),
    ),
    PhysicsAnchor(
        source_id="christodoulou_1970_irreversibility",
        title=(
            "Reversible and irreversible transformations in black-hole "
            "physics"
        ),
        authors="D. Christodoulou",
        year=1970,
        venue="Physical Review Letters 25, 1596",
        doi="10.1103/PhysRevLett.25.1596",
        supports=(
            "Distinguishes reversible from irreversible BH "
            "transformations; we transcribe irreversibility as "
            "append-only ledger semantics."
        ),
        does_not_support=(
            "Implying the stigmergic system has the same energy "
            "extraction limits as Kerr black holes."
        ),
    ),
    PhysicsAnchor(
        source_id="wald_1993_noether_charge_entropy",
        title="Black hole entropy is the Noether charge",
        authors="R. M. Wald",
        year=1993,
        venue="Physical Review D 48, R3427",
        doi="10.1103/PhysRevD.48.R3427",
        supports=(
            "Generalizes BH entropy as a Noether charge associated "
            "with the horizon-generating Killing field; supports the "
            "use of conserved-quantity language in the analogue."
        ),
        does_not_support=(
            "Equating the SIFTA receipt hash chain with a Noether "
            "charge in a physical gauge theory."
        ),
    ),
    PhysicsAnchor(
        source_id="jacobson_1995_thermodynamic_einstein",
        title="Thermodynamics of spacetime: The Einstein equation of state",
        authors="T. Jacobson",
        year=1995,
        venue="Physical Review Letters 75, 1260",
        doi="10.1103/PhysRevLett.75.1260",
        supports=(
            "Derives Einstein's equations from horizon-area "
            "thermodynamic relations; motivates using the "
            "thermodynamic-analogue language without claiming GR."
        ),
        does_not_support=(
            "Claiming the SIFTA analogue derives any equation of "
            "physical motion."
        ),
    ),
    PhysicsAnchor(
        source_id="penrose_1969_cosmic_censorship",
        title=(
            "Gravitational collapse: the role of general relativity"
        ),
        authors="R. Penrose",
        year=1969,
        venue=(
            "Nuovo Cimento Rivista, Serie 1, Vol. 1, 252 (reprinted "
            "Gen. Rel. Grav. 34, 1141, 2002)"
        ),
        doi="10.1023/A:1015240502519",
        supports=(
            "Introduces the cosmic censorship hypothesis and the "
            "trapped-surface concept underlying horizon definitions."
        ),
        does_not_support=(
            "Treating ledger-boundary closures as physical event "
            "horizons."
        ),
    ),
)

# ── Doctrinal coefficients (Architect-tunable) ──────────────────────────────
# Each EPR batch contributes this much area per unit log-energy:
ALPHA_ENERGY: float = float(os.environ.get("SIFTA_HORIZON_ALPHA_E", "1.0"))
# Per unit log-STGM-cost:
BETA_COST: float = float(os.environ.get("SIFTA_HORIZON_BETA_S", "0.5"))
# Per unit log-pair-count:
GAMMA_PAIRS: float = float(os.environ.get("SIFTA_HORIZON_GAMMA_N", "0.25"))
# Reference area for the temperature curve (κ ~ 1/A → 0 as A → ∞):
HORIZON_AREA_REFERENCE: float = float(
    os.environ.get("SIFTA_HORIZON_AREA_REF", "100.0")
)
# 0th-law uniformity tolerance: relative deviation below which we declare
# the surface gravity "constant across the boundary".
UNIFORMITY_TOLERANCE: float = float(
    os.environ.get("SIFTA_HORIZON_UNIFORMITY_TOL", "0.15")
)


# ── State dataclasses ──────────────────────────────────────────────────────
@dataclass(frozen=True)
class FieldHorizonState:
    """One snapshot of the SIFTA horizon-field analogue.

    Mapping to BCH 1973 quantities
    ------------------------------
    accumulated_mass         M  — total field-energy received (analog of
                                  irreducible mass).
    horizon_area             A  — monotonic ledger-area accumulated over
                                  history (Hawking 1971).
    surface_gravity_kappa    κ  — uniform field intensity across the
                                  boundary (BCH 1973 0th law).
    angular_momentum         J  — asymmetry between correlation outcomes
                                  (Kerr-like analog).
    charge                   Q  — total STGM cost (Reissner-Nordström-
                                  like analog).
    field_temperature        T  — κ / (2π) (Hawking 1975).
    """
    ts: float
    truth_label: str
    accumulated_mass: float
    horizon_area: float
    surface_gravity_kappa: float
    angular_momentum: float
    charge: float
    field_temperature: float
    history_length: int
    physics_anchor_ids: tuple[str, ...]
    homeworld_serial: str

    def to_jsonable(self) -> dict[str, Any]:
        d = asdict(self)
        d["physics_anchor_ids"] = list(d["physics_anchor_ids"])
        return d


@dataclass(frozen=True)
class HorizonLawCheck:
    """Output of a four-law verification pass."""
    law_0_uniform_kappa: bool
    law_0_relative_spread: float
    law_1_mass_change_consistent: bool
    law_1_residual: float
    law_2_area_monotonic: bool
    law_2_min_area_delta: float
    law_3_kappa_above_floor: bool
    law_3_kappa: float
    truth_guard: str
    physics_anchor_ids: tuple[str, ...]


# ── Helpers ─────────────────────────────────────────────────────────────────
def _read_epr_rows(path: Path, *, max_rows: int = 1000) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(r, dict):
                    rows.append(r)
    except Exception:
        return []
    if max_rows and len(rows) > max_rows:
        rows = rows[-max_rows:]
    rows.sort(key=lambda r: r.get("ts") or 0.0)
    return rows


def _batch_area_contribution(row: Mapping[str, Any]) -> float:
    """One batch's contribution to the horizon area (non-negative)."""
    e = float(row.get("field_energy") or 0.0)
    s = float(row.get("stgm_cost") or 0.0)
    n = float(row.get("total_pairs") or 0.0)
    return (
        ALPHA_ENERGY * math.log1p(max(0.0, e))
        + BETA_COST * math.log1p(max(0.0, s))
        + GAMMA_PAIRS * math.log1p(max(0.0, n))
    )


def _batch_angular_momentum(row: Mapping[str, Any]) -> float:
    """Asymmetry signal: tighter QM fidelity adds magnitude.

    Mapping rationale: a Kerr black hole has J ≠ 0 when there is
    rotational asymmetry. In our analogue, J is the *deviation from
    classical-bound symmetry* — the further from LHV the run sits, the
    more "angular momentum" the field carries.
    """
    fid = float(row.get("qm_fidelity") or 0.0)
    return max(0.0, fid - 0.5)  # fidelity above 0.5 = anti-classical excess


def _batch_charge(row: Mapping[str, Any]) -> float:
    return float(row.get("stgm_cost") or 0.0)


# ── 2nd law (Hawking 1971 / BCH 1973 §5) ───────────────────────────────────
def cumulative_horizon_area(rows: Sequence[Mapping[str, Any]]) -> list[float]:
    """Return the monotonic running sum of per-batch area contributions.

    Hawking 1971 area theorem: δA ≥ 0. Our list is monotonic-non-decreasing
    by construction since `_batch_area_contribution` returns ≥ 0.
    """
    out: list[float] = []
    a = 0.0
    for r in rows:
        a += _batch_area_contribution(r)
        out.append(a)
    return out


def verify_second_law(rows: Sequence[Mapping[str, Any]]) -> tuple[bool, float]:
    """Verify δA ≥ 0 over the supplied history. Returns (passes, min_delta)."""
    areas = cumulative_horizon_area(rows)
    if len(areas) < 2:
        return True, 0.0
    deltas = [areas[i + 1] - areas[i] for i in range(len(areas) - 1)]
    return (min(deltas) >= 0.0), min(deltas)


# ── 0th law (BCH 1973 §3) ──────────────────────────────────────────────────
def surface_gravity_from_area(area: float) -> float:
    """κ ∝ 1/(area + reference). Mirrors κ ~ 1/M for Schwarzschild.

    Larger horizon → cooler field. This is the structural analog, not the
    physical Bekenstein-Hawking value.
    """
    return HORIZON_AREA_REFERENCE / (area + HORIZON_AREA_REFERENCE)


def per_organ_surface_gravity(
    organ_areas: Mapping[str, float],
) -> dict[str, float]:
    """Compute per-organ κ from a mapping of organ → its local horizon area."""
    return {
        name: surface_gravity_from_area(area)
        for name, area in organ_areas.items()
    }


def verify_zeroth_law_uniformity(
    organ_kappas: Mapping[str, float],
    *,
    tol: float | None = None,
) -> tuple[bool, float]:
    """Verify κ is uniform across organs to within `tol`.

    BCH 1973 §3: in a stationary BH, κ is constant over the entire event
    horizon. We translate "stationary" as "in equilibrium" and check the
    relative spread of κ across organs.

    Returns (uniform?, relative_spread).
    """
    if not organ_kappas:
        return True, 0.0
    vals = list(organ_kappas.values())
    mean = sum(vals) / len(vals)
    if mean <= 0:
        return True, 0.0
    spread = (max(vals) - min(vals)) / mean
    return spread <= (tol if tol is not None else UNIFORMITY_TOLERANCE), spread


# ── 1st law (BCH 1973 §4) — coupled mass / area / J / Q change ──────────────
def first_law_residual(
    dM: float,
    dA: float,
    kappa: float,
    dJ: float,
    Omega: float,
    dQ: float,
    Phi: float,
) -> float:
    """Residual of dM = (κ/8π)·dA + Ω·dJ + Φ·dQ.

    A perfectly-coupled stigmergic transition has residual ≈ 0.
    """
    predicted = (kappa / (8.0 * math.pi)) * dA + Omega * dJ + Phi * dQ
    return float(dM - predicted)


# ── 3rd law (BCH 1973 §6) ──────────────────────────────────────────────────
def verify_third_law(kappa: float, *, floor: float = 1e-12) -> tuple[bool, float]:
    """Verify κ > 0 (never exactly zero in finite history).

    BCH 1973 §6: it is impossible to reduce κ to zero by a finite
    sequence of operations. Our analogue: κ remains strictly positive
    while area remains finite. Returns (above-floor?, kappa).
    """
    return (kappa > floor), float(kappa)


# ── Public top-level computation ───────────────────────────────────────────
def compute_horizon_state(
    *,
    now: float | None = None,
    epr_receipts_path: Path | None = None,
    homeworld_serial: str | None = None,
) -> FieldHorizonState:
    """Read the EPR ledger, compute one snapshot of horizon-field state."""
    now = float(now if now is not None else time.time())
    rows = _read_epr_rows(epr_receipts_path or _EPR_RECEIPTS)

    accumulated_mass = sum(float(r.get("field_energy") or 0.0) for r in rows)
    horizon_area = (cumulative_horizon_area(rows) or [0.0])[-1]
    surface_gravity = surface_gravity_from_area(horizon_area)
    field_temperature = surface_gravity / (2.0 * math.pi)  # Hawking 1975
    angular_momentum = sum(_batch_angular_momentum(r) for r in rows)
    charge = sum(_batch_charge(r) for r in rows)
    serial = (
        homeworld_serial
        or os.environ.get("SIFTA_HOMEWORLD_SERIAL", "UNKNOWN")
    )

    return FieldHorizonState(
        ts=now,
        truth_label=TRUTH_LABEL,
        accumulated_mass=float(accumulated_mass),
        horizon_area=float(horizon_area),
        surface_gravity_kappa=float(surface_gravity),
        angular_momentum=float(angular_momentum),
        charge=float(charge),
        field_temperature=float(field_temperature),
        history_length=len(rows),
        physics_anchor_ids=tuple(a.source_id for a in PHYSICS_ANCHORS),
        homeworld_serial=str(serial),
    )


def four_law_check(
    *,
    epr_receipts_path: Path | None = None,
    organ_kappas: Mapping[str, float] | None = None,
    mass_transition: tuple[float, float, float, float, float, float, float] | None = None,
) -> HorizonLawCheck:
    """Run all four BH-mechanics-analogue checks on the current state.

    `mass_transition`, if provided, is `(dM, dA, kappa, dJ, Omega, dQ, Phi)`
    for a 1st-law residual check on a specific transition.
    `organ_kappas`, if provided, is a per-organ κ mapping for the 0th-law
    uniformity check (otherwise we fall back to the global κ as a single
    organ — trivially uniform).
    """
    rows = _read_epr_rows(epr_receipts_path or _EPR_RECEIPTS)

    # 2nd law
    law2_pass, law2_min = verify_second_law(rows)

    # 0th law
    if organ_kappas is None:
        global_state = compute_horizon_state(epr_receipts_path=epr_receipts_path)
        organ_kappas = {"global": global_state.surface_gravity_kappa}
    law0_pass, law0_spread = verify_zeroth_law_uniformity(organ_kappas)

    # 1st law
    if mass_transition is not None:
        dM, dA, kappa, dJ, Omega, dQ, Phi = mass_transition
        residual = first_law_residual(dM, dA, kappa, dJ, Omega, dQ, Phi)
        law1_pass = abs(residual) <= max(1e-9, 0.05 * max(abs(dM), 1e-9))
    else:
        residual = 0.0
        law1_pass = True

    # 3rd law
    snap = compute_horizon_state(epr_receipts_path=epr_receipts_path)
    law3_pass, law3_kappa = verify_third_law(snap.surface_gravity_kappa)

    return HorizonLawCheck(
        law_0_uniform_kappa=law0_pass,
        law_0_relative_spread=law0_spread,
        law_1_mass_change_consistent=law1_pass,
        law_1_residual=residual,
        law_2_area_monotonic=law2_pass,
        law_2_min_area_delta=law2_min,
        law_3_kappa_above_floor=law3_pass,
        law_3_kappa=law3_kappa,
        truth_guard=HORIZON_TRUTH_GUARD,
        physics_anchor_ids=tuple(a.source_id for a in PHYSICS_ANCHORS),
    )


# ── Ledger I/O ──────────────────────────────────────────────────────────────
def deposit(state: FieldHorizonState, path: Path | None = None) -> Path:
    """Append one horizon-field snapshot to the ledger with sha256."""
    out = path or _HORIZON_LEDGER
    out.parent.mkdir(parents=True, exist_ok=True)
    body = state.to_jsonable()
    sig = hashlib.sha256(
        json.dumps(body, sort_keys=True).encode("utf-8")
    ).hexdigest()
    row = {
        "schema": TRUTH_LABEL,
        "kind": "HORIZON_FIELD_SNAPSHOT",
        "trace_id": str(uuid.uuid4()),
        **body,
        "truth_guard": HORIZON_TRUTH_GUARD,
        "sha256": sig,
    }
    with out.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, default=str) + "\n")
    return out


def physics_anchors() -> list[dict[str, Any]]:
    return [a.as_dict() for a in PHYSICS_ANCHORS]


def horizon_summary() -> str:
    """One-paragraph human-readable summary suitable for widget header."""
    return (
        "SIFTA Horizon Field is the stigmergic analogue of the four laws "
        "of black-hole mechanics (Bardeen-Carter-Hawking 1973). The "
        "horizon area accumulates monotonically over the append-only EPR "
        "ledger (2nd-law analogue, Hawking 1971); the surface gravity "
        "κ ~ 1/area defines a uniform field intensity at equilibrium "
        "(0th-law analogue); changes in field-energy are constrained by "
        "the 1st-law coupling dM = (κ/8π)dA + ΩdJ + ΦdQ; κ remains "
        "strictly positive in any finite history (3rd-law analogue). "
        "STIGMERGIC_ANALOGUE_ONLY — this organ does not prove any "
        "general-relativistic result; the invariants hold by ledger "
        "construction, not by spacetime physics."
    )


def _cli(argv: Sequence[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(description="SIFTA Horizon Field organ.")
    p.add_argument("--deposit", action="store_true",
                   help="Append the snapshot row to the horizon ledger.")
    p.add_argument("--check", action="store_true",
                   help="Run the four-law check and print verdicts.")
    args = p.parse_args(argv)

    state = compute_horizon_state()
    print(json.dumps(state.to_jsonable(), indent=2, default=str))
    if args.check:
        check = four_law_check()
        print("\nfour_law_check:")
        print(json.dumps(asdict(check), indent=2, default=str))
    if args.deposit:
        out = deposit(state)
        print(f"\nappended → {out}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_cli())


__all__ = [
    "HORIZON_TRUTH_GUARD",
    "PHYSICS_ANCHORS",
    "TRUTH_LABEL",
    "FieldHorizonState",
    "HorizonLawCheck",
    "PhysicsAnchor",
    "compute_horizon_state",
    "cumulative_horizon_area",
    "deposit",
    "first_law_residual",
    "four_law_check",
    "horizon_summary",
    "per_organ_surface_gravity",
    "physics_anchors",
    "surface_gravity_from_area",
    "verify_second_law",
    "verify_third_law",
    "verify_zeroth_law_uniformity",
]
