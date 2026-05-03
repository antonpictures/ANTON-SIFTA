"""
Event 148 — Tumor-Immune Stigmergic Proof Lab.

Synthetic-only research sandbox for disciplined tumor-immune dynamics. This
module does not ingest PHI, does not emit clinical advice, and does not propose
therapy. It translates a toy tumor-immune field into SIFTA's Event 137
TREM2/CD33 two-signal receipt so the organism can run a falsifiable dynamical
story with append-only evidence.

Ledger:
  .sifta_state/tumor_immune_stigmergic_lab.jsonl
  truth_label == "TIN_SIM_TICK"

Allowed data origins:
  synthetic
  licensed_public
"""
from __future__ import annotations

import json
import math
import time
import uuid
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from System.jsonl_file_lock import append_line_locked, read_text_locked
from System.swarm_microglia_synaptic_pruner import compute_two_signal_pressure
from System.swarm_persistent_owner_history import state_dir

EVENT_ID = 148
LOG_NAME = "tumor_immune_stigmergic_lab.jsonl"
TRUTH_LABEL = "TIN_SIM_TICK"
ALLOWED_DATA_ORIGINS = {"synthetic", "licensed_public"}
NON_GOALS = (
    "no_phi",
    "no_patient_identifiers",
    "no_therapy_recommendations",
    "synthetic_or_licensed_public_only",
)
PHI_KEYS = {
    "patient",
    "patient_id",
    "patient_name",
    "mrn",
    "medical_record_number",
    "dob",
    "date_of_birth",
    "ssn",
    "phone",
    "address",
    "email",
}
FORBIDDEN_RECEIPT_PHRASES = (
    "therapy recommendation",
    "clinical recommendation",
    "dose",
    "dosage",
    "prescribe",
    "treat this patient",
)


def lab_log_path(root: Optional[Path] = None) -> Path:
    return state_dir(root) / LOG_NAME


def _clamp01(value: Any, default: float = 0.0) -> float:
    try:
        x = float(value)
    except (TypeError, ValueError):
        x = default
    return min(1.0, max(0.0, x))


@dataclass(frozen=True)
class TumorImmuneState:
    """Bounded synthetic state vector for one toy tumor-immune field."""

    tumor_burden: float = 0.62
    antigen_visibility: float = 0.42
    cart_effector_load: float = 0.28
    cart_persistence: float = 0.50
    tme_suppression: float = 0.56
    hypoxia: float = 0.48
    exhaustion: float = 0.30
    cytokine_risk: float = 0.18
    off_target_risk: float = 0.08

    def bounded(self) -> "TumorImmuneState":
        return replace(
            self,
            tumor_burden=_clamp01(self.tumor_burden),
            antigen_visibility=_clamp01(self.antigen_visibility),
            cart_effector_load=_clamp01(self.cart_effector_load),
            cart_persistence=_clamp01(self.cart_persistence),
            tme_suppression=_clamp01(self.tme_suppression),
            hypoxia=_clamp01(self.hypoxia),
            exhaustion=_clamp01(self.exhaustion),
            cytokine_risk=_clamp01(self.cytokine_risk),
            off_target_risk=_clamp01(self.off_target_risk),
        )


def default_synthetic_state() -> TumorImmuneState:
    return TumorImmuneState().bounded()


def _walk_keys(obj: Any) -> Iterable[str]:
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield str(key)
            yield from _walk_keys(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk_keys(item)


def assert_synthetic_contract(
    *,
    data_origin: str = "synthetic",
    payload: Optional[Dict[str, Any]] = None,
) -> None:
    """Reject non-synthetic/non-public data and common PHI key shapes."""
    if data_origin not in ALLOWED_DATA_ORIGINS:
        raise ValueError(
            f"Tumor-immune lab accepts only {sorted(ALLOWED_DATA_ORIGINS)} data_origin, got {data_origin!r}"
        )
    if not payload:
        return
    keys = {k.lower() for k in _walk_keys(payload)}
    hit = sorted(PHI_KEYS & keys)
    if hit:
        raise ValueError(f"PHI-like keys are not allowed in synthetic proof lab payloads: {hit}")


def classify_field_regime(state: TumorImmuneState) -> str:
    state = state.bounded()
    if state.tumor_burden > 0.70 and state.antigen_visibility < 0.35:
        return "COLD_SUPPRESSED"
    if state.antigen_visibility > 0.60 and state.cart_effector_load > 0.45 and state.cytokine_risk < 0.55:
        return "HOT_CONTROLLED"
    if state.cytokine_risk >= 0.65 or state.off_target_risk >= 0.55:
        return "TOXICITY_RISK"
    if state.tme_suppression > 0.65:
        return "SUPPRESSIVE_TME"
    return "MIXED"


def apply_toy_intervention(
    state: TumorImmuneState,
    intervention_id: str = "none",
) -> TumorImmuneState:
    """
    Apply one bounded synthetic do(intervention).

    These labels are toy knobs for the sandbox and intentionally avoid clinical
    instructions. They do not encode a treatment protocol.
    """
    s = state.bounded()
    if intervention_id in ("", "none", "observe"):
        return s
    if intervention_id == "toy_trem2_blockade":
        return replace(
            s,
            tme_suppression=s.tme_suppression - 0.12,
            antigen_visibility=s.antigen_visibility + 0.04,
            cytokine_risk=s.cytokine_risk + 0.03,
        ).bounded()
    if intervention_id == "toy_cart_persistence":
        return replace(
            s,
            cart_persistence=s.cart_persistence + 0.14,
            cart_effector_load=s.cart_effector_load + 0.08,
            exhaustion=s.exhaustion + 0.03,
            cytokine_risk=s.cytokine_risk + 0.04,
        ).bounded()
    if intervention_id == "toy_logic_gate_focus":
        return replace(
            s,
            antigen_visibility=s.antigen_visibility + 0.12,
            off_target_risk=s.off_target_risk - 0.04,
            cytokine_risk=s.cytokine_risk - 0.02,
        ).bounded()
    if intervention_id == "toy_tme_release":
        return replace(
            s,
            tme_suppression=s.tme_suppression - 0.10,
            hypoxia=s.hypoxia - 0.04,
            antigen_visibility=s.antigen_visibility + 0.03,
        ).bounded()
    raise ValueError(f"Unknown synthetic intervention_id: {intervention_id!r}")


def remap_to_microglia_inputs(state: TumorImmuneState) -> Dict[str, Any]:
    """
    Toy field remap from §10.14.27.4 into Event 137 two-signal inputs.

    tumor burden         -> inverse usage_count
    CAR-T effector load  -> recent_high_value_usage
    TGF-beta/PD-L1 proxy -> pruning_conservatism/protection_score
    hypoxia              -> contradiction/damage pressure
    """
    s = state.bounded()
    usage_count = int(round((1.0 - s.tumor_burden) * 8.0))
    reward_proxy = 0.40 * (1.0 - s.tumor_burden) - 0.40 * s.cytokine_risk - 0.20 * s.hypoxia
    return {
        "age_hours": 96.0 * s.tumor_burden,
        "usage_count": usage_count,
        "recent_reward_mean": max(-1.0, min(1.0, reward_proxy)),
        "recent_regret": _clamp01(0.45 * s.tumor_burden + 0.35 * s.hypoxia + 0.20 * s.exhaustion),
        "wm_contradiction_pe": _clamp01(0.70 * s.hypoxia + 0.30 * (1.0 - s.antigen_visibility)),
        "homeostatic_pressure": _clamp01(0.60 * s.tumor_burden + 0.40 * s.exhaustion),
        "protection_score": _clamp01(0.70 * s.tme_suppression + 0.30 * s.off_target_risk),
        "pruning_conservatism": _clamp01(0.80 * s.tme_suppression + 0.20 * s.off_target_risk),
        "recent_high_value_usage": _clamp01(s.cart_effector_load),
        "currently_active_in_arbiter": bool(s.cart_effector_load > 0.45),
        "stability_ok": bool(s.cytokine_risk < 0.70),
        "stability_dwell_score": _clamp01(1.0 - s.cytokine_risk),
        "goal_alignment": _clamp01(s.antigen_visibility),
        "owner_frustration": 0.0,
        "clamp_level": "RATE_LIMIT" if s.cytokine_risk >= 0.55 else "NONE",
        "na_level": _clamp01(0.35 + 0.35 * s.hypoxia + 0.30 * s.cytokine_risk),
        "valence": max(-1.0, min(1.0, 1.0 - 2.0 * s.tumor_burden - s.cytokine_risk)),
    }


def two_signal_snapshot_for_state(state: TumorImmuneState) -> Dict[str, Any]:
    inputs = remap_to_microglia_inputs(state)
    return compute_two_signal_pressure(**inputs)


def tick_state(
    state: TumorImmuneState,
    *,
    intervention_id: str = "none",
    dt: float = 1.0,
) -> tuple[TumorImmuneState, Dict[str, float]]:
    """Advance one synthetic tick and return the new state plus dynamics."""
    pre = apply_toy_intervention(state, intervention_id).bounded()
    immune_pressure = _clamp01(
        pre.antigen_visibility
        * pre.cart_effector_load
        * pre.cart_persistence
        * (1.0 - pre.tme_suppression)
        * (1.0 - 0.65 * pre.exhaustion)
    )
    tumor_growth = pre.tumor_burden * (0.065 + 0.055 * pre.hypoxia + 0.050 * pre.tme_suppression)
    tumor_kill = pre.tumor_burden * (0.24 * immune_pressure)
    new_tumor = _clamp01(pre.tumor_burden + dt * (tumor_growth * (1.0 - pre.tumor_burden) - tumor_kill))
    new_cart = _clamp01(
        pre.cart_effector_load
        + dt * (0.050 * pre.antigen_visibility * pre.cart_persistence - 0.035 * pre.exhaustion - 0.020 * pre.cytokine_risk)
    )
    new_exhaustion = _clamp01(pre.exhaustion + dt * (0.045 * pre.tme_suppression + 0.030 * new_cart - 0.030 * pre.cart_persistence))
    new_hypoxia = _clamp01(pre.hypoxia + dt * (0.040 * new_tumor - 0.030 * immune_pressure))
    new_suppression = _clamp01(pre.tme_suppression + dt * (0.035 * new_tumor + 0.020 * new_hypoxia - 0.035 * immune_pressure))
    new_antigen = _clamp01(pre.antigen_visibility + dt * (0.030 * immune_pressure - 0.030 * new_suppression - 0.020 * new_hypoxia))
    new_cytokine = _clamp01(0.08 + 0.55 * new_cart * max(0.10, new_antigen) + 0.18 * pre.off_target_risk)
    new_persistence = _clamp01(pre.cart_persistence + dt * (0.020 * new_antigen - 0.025 * new_exhaustion))
    new_state = TumorImmuneState(
        tumor_burden=new_tumor,
        antigen_visibility=new_antigen,
        cart_effector_load=new_cart,
        cart_persistence=new_persistence,
        tme_suppression=new_suppression,
        hypoxia=new_hypoxia,
        exhaustion=new_exhaustion,
        cytokine_risk=new_cytokine,
        off_target_risk=pre.off_target_risk,
    ).bounded()
    dynamics = {
        "immune_pressure": round(immune_pressure, 6),
        "tumor_growth": round(tumor_growth, 6),
        "tumor_kill": round(tumor_kill, 6),
        "delta_tumor": round(new_state.tumor_burden - state.tumor_burden, 6),
        "response_proxy": round(max(0.0, state.tumor_burden - new_state.tumor_burden), 6),
        "safety_proxy": round(1.0 - new_state.cytokine_risk, 6),
    }
    return new_state, dynamics


def _assert_receipt_text_safe(row: Dict[str, Any]) -> None:
    text = json.dumps(row, sort_keys=True).lower()
    for phrase in FORBIDDEN_RECEIPT_PHRASES:
        if phrase in text:
            raise ValueError(f"Forbidden clinical phrase in tumor-immune receipt: {phrase}")


def run_tin_tick(
    state: Optional[TumorImmuneState] = None,
    *,
    intervention_id: str = "none",
    tick_id: Optional[int] = None,
    data_origin: str = "synthetic",
    payload: Optional[Dict[str, Any]] = None,
    root: Optional[Path] = None,
    write_ledger: bool = True,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """Run one synthetic tumor-immune tick and optionally append a TIN receipt."""
    assert_synthetic_contract(data_origin=data_origin, payload=payload)
    start = (state or default_synthetic_state()).bounded()
    next_state, dynamics = tick_state(start, intervention_id=intervention_id)
    two_signal = two_signal_snapshot_for_state(next_state)
    row: Dict[str, Any] = {
        "ts": now or time.time(),
        "trace_id": str(uuid.uuid4()),
        "event_id": EVENT_ID,
        "kind": TRUTH_LABEL,
        "truth_label": TRUTH_LABEL,
        "tick_id": tick_id,
        "data_origin": data_origin,
        "synthetic_only": True,
        "non_goals": list(NON_GOALS),
        "intervention_id": intervention_id,
        "causal_do": {
            "enabled": intervention_id not in ("", "none", "observe"),
            "intervention_id": intervention_id,
            "allowed_scope": sorted(ALLOWED_DATA_ORIGINS),
        },
        "state_before": asdict(start),
        "state_after": asdict(next_state),
        "field_regime": classify_field_regime(next_state),
        "toy_field_remap": remap_to_microglia_inputs(next_state),
        "dynamics": dynamics,
        "two_signal_snapshot": two_signal,
        "safety_clause": "Synthetic sandbox only; no PHI; no clinical guidance; no treatment instructions.",
        "provenance": (
            "Dunn2002NatImmunol; Schreiber2011Science; Keren-Shaul2017Cell; "
            "Roybal2016Cell; Fedorov2013SciTranslMed; Lee2014Blood; "
            "Wherry&Kurachi2015NatRevImmunol; Majzner&Mackall2019NatRevCancer; "
            "Event137_TREM2_CD33_two_signal"
        ),
    }
    _assert_receipt_text_safe(row)
    if write_ledger:
        append_line_locked(
            lab_log_path(root),
            json.dumps(row, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return row


def simulate_tin_trajectory(
    *,
    ticks: int = 8,
    initial_state: Optional[TumorImmuneState] = None,
    intervention_schedule: Optional[Dict[int, str]] = None,
    data_origin: str = "synthetic",
    root: Optional[Path] = None,
    write_ledger: bool = True,
) -> List[Dict[str, Any]]:
    assert_synthetic_contract(data_origin=data_origin)
    state = (initial_state or default_synthetic_state()).bounded()
    rows: List[Dict[str, Any]] = []
    schedule = dict(intervention_schedule or {})
    for tick in range(max(0, int(ticks))):
        intervention = schedule.get(tick, "none")
        row = run_tin_tick(
            state,
            intervention_id=intervention,
            tick_id=tick,
            data_origin=data_origin,
            root=root,
            write_ledger=write_ledger,
        )
        rows.append(row)
        state = TumorImmuneState(**row["state_after"]).bounded()
    return rows


def tail_lab_rows(max_rows: int = 12, *, root: Optional[Path] = None) -> List[Dict[str, Any]]:
    path = lab_log_path(root)
    if not path.exists():
        return []
    raw = read_text_locked(path, encoding="utf-8", errors="replace")
    rows: List[Dict[str, Any]] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows[-max(1, min(max_rows, 200)) :]


def summary_for_prompt(*, root: Optional[Path] = None) -> str:
    rows = tail_lab_rows(1, root=root)
    if not rows:
        return ""
    row = rows[-1]
    after = row.get("state_after") or {}
    dyn = row.get("dynamics") or {}
    two = row.get("two_signal_snapshot") or {}
    return (
        "TUMOR-IMMUNE STIGMERGIC LAB (Event 148 synthetic-only): "
        f"regime={row.get('field_regime')} "
        f"tumor={float(after.get('tumor_burden', 0.0)):.3f} "
        f"immune_pressure={float(dyn.get('immune_pressure', 0.0)):.3f} "
        f"TREM2={two.get('damage_score')} CD33={two.get('inhibition_signal')} "
        "nonclinical sandbox"
    )


__all__ = [
    "ALLOWED_DATA_ORIGINS",
    "EVENT_ID",
    "NON_GOALS",
    "TRUTH_LABEL",
    "TumorImmuneState",
    "apply_toy_intervention",
    "assert_synthetic_contract",
    "classify_field_regime",
    "default_synthetic_state",
    "lab_log_path",
    "remap_to_microglia_inputs",
    "run_tin_tick",
    "simulate_tin_trajectory",
    "summary_for_prompt",
    "tail_lab_rows",
    "tick_state",
    "two_signal_snapshot_for_state",
]
