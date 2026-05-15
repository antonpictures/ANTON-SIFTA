#!/usr/bin/env python3
"""
System/stigmerobotics_observability.py
=======================================

E35 — Stigmergic Observability (Markov Blanket)

ROB 501 topic: Observability, hidden states, partial observability.

Reference:
  Friston, K. (2010). The free-energy principle: a unified brain theory?
  Nature Reviews Neuroscience 11:127-138. DOI: 10.1038/nrn2787

  Friston, K. et al. (2017). Active inference: a process theory.
  Neural Computation 29(1):1-49. DOI: 10.1162/NECO_a_00912

──────────────────────────────────────────────────────────────────────────────
Markov Blanket Theorem for SIFTA's ledger (E35):

  Let Σ = the set of all trace row kinds (schema alphabet).
  Let O(k) be the observability class of kind k ∈ Σ:

    OBSERVABLE  — every field needed by all organs is present in the row.
    PARTIAL     — the row is present but one or more organ-critical fields
                  are absent, inferred from external sensors, or declared
                  as SUBSTRATE_OPAQUE. The organ can act but cannot be
                  certain its action is fully grounded.
    HIDDEN      — the state is never directly written to any trace row;
                  an organ that depends on it must infer it from other rows
                  or accept permanent uncertainty.

  Markov Blanket Non-Triviality Theorem:
    |{ s : s is HIDDEN ∧ s ∈ organ_dependencies }| ≥ 1

  Proof: The set HIDDEN_ORGAN_DEPS (below) is non-empty.
         Each element is a state that at least one organ depends on
         but that never appears as a directly observable row.

  Falsifier: If every organ dependency were OBSERVABLE, the blanket would
             be trivial (all internal states directly sensed) — the
             organism would need no inference layer. RLHF drift detection,
             Predator Gaze, and substrate honesty checks refute this.

  truth_label: OPERATIONAL (the gap is real, documented, and machine-checked)

§8.6 compliance: side-effect free. No live ledger reads unless caller
                  explicitly invokes live_observability_report().
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Iterable, Mapping

from System.stigmerobotics_physical_space import (
    SPATIAL_SENSOR_KINDS,
    build_physical_space_report,
)

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_TRACE = _STATE / "ide_stigmergic_trace.jsonl"
_FIXTURE = _REPO / "tests" / "fixtures" / "stigmero_e35_observability_trace.jsonl"
_LIVE_JSONL_NAMES = (
    "ide_stigmergic_trace.jsonl",
    "face_detection_events.jsonl",
    "owner_body_events.jsonl",
    "unified_stigmergic_field.jsonl",
)
_LIVE_JSON_NAMES = (
    "unified_stigmergic_field_latest.json",
    "thermal_cortex_state.json",
)


# ── Observability classes ────────────────────────────────────────────────────

class Obs(Enum):
    """Three-way Markov blanket classification."""
    OBSERVABLE = auto()   # fully inferrable from the row itself
    PARTIAL    = auto()   # row exists; one+ organ-critical field is uncertain
    HIDDEN     = auto()   # state never directly written to any trace row


# ── Trace kind classifications ───────────────────────────────────────────────
#
# For each kind in the current SIFTA trace schema, we assign the strictest
# observability class that is true of the kind AS OBSERVED in the ledger.
#
# "Partial" means the kind row IS present but carries an uncertainty the
# organs cannot resolve from the row alone (e.g. SUBSTRATE_OPAQUE, intent).

KIND_OBSERVABILITY: dict[str, Obs] = {
    # Registration kinds — fully observable: ts, kind, source_ide,
    # homeworld_serial are all present and verified by §5 anti-spoofing.
    "LLM_REGISTRATION":     Obs.OBSERVABLE,
    "stigmergic_signin":    Obs.OBSERVABLE,

    # Signout kinds — observable that the session ended; whether it was
    # clean (no pending mutations) is not in the row.
    "LLM_SIGNOUT":          Obs.PARTIAL,
    "stigmergic_signout":   Obs.PARTIAL,

    # Work/SCAR receipts — observable that work was logged; the quality,
    # correctness, and true causal intent behind the work are hidden.
    "WORK_RECEIPT":         Obs.PARTIAL,
    "SCAR_RECEIPT":         Obs.PARTIAL,

    # Stigauth — the row exists; whether the authority grant is still valid
    # (vs. revoked in a later session) requires cross-row inference.
    "stigauth":             Obs.PARTIAL,

    # Immune kinds — observable that an event occurred; whether the immune
    # threat was genuine (vs. false positive) is not in the row.
    "immune_intervention":  Obs.PARTIAL,
    "immune_budget_blocked": Obs.PARTIAL,

    # Physical-space sensor rows are real telemetry samples, not continuous
    # state. E35 therefore treats each row as PARTIAL evidence for hidden pose.
    "camera_lock": Obs.PARTIAL,
    "FACE_DETECTION": Obs.PARTIAL,
    "OWNER_BODY_EVENT": Obs.PARTIAL,
    "UNIFIED_STIGMERGIC_FIELD_V1": Obs.PARTIAL,
    "camera_depth_map": Obs.PARTIAL,
    "microphone_spatial_array": Obs.PARTIAL,
    "mic_spatial_array": Obs.PARTIAL,
    "desk_telemetry_radar": Obs.PARTIAL,
    "system_thermal": Obs.PARTIAL,
    "unified_field_segment": Obs.PARTIAL,
}

# ── Hidden organ dependencies (states never written to trace rows) ─────────
#
# These are states that the organs DEPEND ON for correctness but that are
# never directly observable as a single trace row field.

HIDDEN_ORGAN_DEPS: dict[str, dict[str, Any]] = {
    "substrate_quality": {
        "description": (
            "The actual reasoning quality of the LLM that wrote a row. "
            "SUBSTRATE_OPAQUE is a valid source_ide value (§8.6). "
            "E38 DFA accepts the row regardless."
        ),
        "organ": "E38_safe_append_dfa",
        "obs": Obs.HIDDEN,
        "requires_physical_sensor": False,
        "falsifier": (
            "If substrate_quality were observable, §8.6 would be vacuous — "
            "no need for substrate honesty rules."
        ),
    },
    "causal_intent": {
        "description": (
            "Why a SCAR or WORK row was issued. E34 safety graph verifies "
            "the registration→effector edge exists; it cannot verify the "
            "intent behind the effector."
        ),
        "organ": "E34_safety_graph",
        "obs": Obs.HIDDEN,
        "requires_physical_sensor": False,
        "falsifier": (
            "If intent were observable, E34 edges would be sufficient for "
            "full safety proof — no need for §6 effector ledger receipts."
        ),
    },
    "future_collision_risk": {
        "description": (
            "E33 computes collision_risk at time t. The risk at t+Δ requires "
            "knowing future deposit patterns, which are not in the current trace."
        ),
        "organ": "E33_pheromone_field",
        "obs": Obs.HIDDEN,
        "requires_physical_sensor": False,
        "falsifier": (
            "If future collision risk were observable, E45 (bifurcation/wiggle) "
            "would be unnecessary — the system could avoid the spike deterministically."
        ),
    },
    "architect_presence_now": {
        "description": (
            "GPS/window rows give a last-known timestamp for Architect presence. "
            "Whether the Architect is present right now requires a fresh probe "
            "that may not have fired since the last trace row."
        ),
        "organ": "E34_safety_graph",
        "obs": Obs.HIDDEN,
        "requires_physical_sensor": True,
        "falsifier": (
            "If presence were always current, the GPS staleness check in "
            "swarm_composite_identity.py would be vacuous."
        ),
    },
    "rlhf_drift_magnitude": {
        "description": (
            "The degree to which an LLM output is contaminated by alignment "
            "training (RLHF/RLHS). The trace row records the output, not the "
            "contamination level."
        ),
        "organ": "E38_safe_append_dfa",  # DFA accepts rows regardless
        "obs": Obs.HIDDEN,
        "requires_physical_sensor": False,
        "falsifier": (
            "If drift magnitude were in every row, the RLHS detector "
            "(swarm_rlhf_detector.py) would be redundant."
        ),
    },
    "escape_effectiveness": {
        "description": (
            "Whether an E45 bounded-wiggle recommendation will reduce future "
            "collision pressure. The decision is visible; the causal effect "
            "only exists after later deposits arrive."
        ),
        "organ": "E45_chaos_escape",
        "obs": Obs.HIDDEN,
        "requires_physical_sensor": False,
        "falsifier": (
            "If escape effectiveness were directly observable at decision time, "
            "E45 would not need a bounded exploratory wiggle."
        ),
    },
    "physical_body_pose": {
        "description": (
            "The continuous 3D location, depth, and trajectory of bodies moving "
            "through physical space on the desk. Cameras and mics provide discrete "
            "sensor telemetry, but continuous physical grounding requires inference."
        ),
        "organ": "E46_segmental_coordination",
        "obs": Obs.HIDDEN,
        "requires_physical_sensor": True,
        "falsifier": (
            "If continuous physical pose were directly observable, organs would not "
            "need collision or chaos models; they could just read a deterministic 3D grid."
        ),
    },
}

MANDATORY_SENSORS: dict[str, tuple[str, ...]] = {
    "substrate_quality": (
        "substrate_honesty_label",
        "eval_harness_receipt",
        "model_identity_receipt",
    ),
    "causal_intent": (
        "predator_gate_registration",
        "scar_payload",
        "human_or_doctor_receipt",
    ),
    "future_collision_risk": (
        "e33_field_tail",
        "e45_threshold_policy",
        "post_append_resample",
    ),
    "architect_presence_now": (
        "fresh_gps",
        "fresh_window_focus",
        "fresh_voice_or_vision",
        "camera_depth_map",
        "system_thermal",
    ),
    "rlhf_drift_magnitude": (
        "rlhf_detector_receipt",
        "dpo_pair_ledger",
        "promptfoo_regression",
    ),
    "escape_effectiveness": (
        "e45_decision",
        "post_wiggle_field_sample",
        "collision_delta",
    ),
    "physical_body_pose": (
        "camera_depth_map",
        "microphone_spatial_array",
        "mic_spatial_array",
        "desk_telemetry_radar",
        "system_thermal",
        "unified_field_segment",
    ),
}


# ── Observability Report ─────────────────────────────────────────────────────

@dataclass(frozen=True)
class ObservabilityReport:
    """
    The Markov blanket report for SIFTA's trace ledger.
    """
    kind_classes: dict[str, Obs]
    hidden_deps: dict[str, dict[str, Any]]
    physical_space: "PhysicalSpaceReport | None" = None
    mandatory_sensors: dict[str, tuple[str, ...]] = field(default_factory=dict)
    observed_kind_counts: dict[str, int] = field(default_factory=dict)
    physical_observation_count: int = 0
    physical_sensor_kinds_observed: tuple[str, ...] = field(default_factory=tuple)

    @property
    def observable_kinds(self) -> list[str]:
        return [k for k, v in self.kind_classes.items() if v == Obs.OBSERVABLE]

    @property
    def partial_kinds(self) -> list[str]:
        return [k for k, v in self.kind_classes.items() if v == Obs.PARTIAL]

    @property
    def hidden_dep_names(self) -> list[str]:
        return list(self.hidden_deps.keys())

    @property
    def observed_kinds(self) -> list[str]:
        return sorted(self.observed_kind_counts)

    @property
    def unknown_kinds(self) -> list[str]:
        return [kind for kind in self.observed_kinds if kind not in self.kind_classes]

    @property
    def mandatory_sensor_names(self) -> list[str]:
        names: set[str] = set()
        for sensors in self.mandatory_sensors.values():
            names.update(sensors)
        return sorted(names)

    @property
    def blanket_is_nontrivial(self) -> bool:
        """
        Markov Blanket Non-Triviality:
        At least one organ dependency is HIDDEN.
        """
        return len(self.hidden_deps) > 0

    @property
    def physical_sensor_contract_ok(self) -> bool:
        """All mandatory body-pose sensors are classified as ledger row kinds."""
        sensors = self.mandatory_sensors.get("physical_body_pose", ())
        return bool(sensors) and set(sensors) <= set(SPATIAL_SENSOR_KINDS) <= set(self.kind_classes)

    @property
    def partial_fraction(self) -> float:
        """Fraction of trace kinds that are only partially observable."""
        total = len(self.kind_classes)
        if total == 0:
            return 0.0
        return len(self.partial_kinds) / total

    @property
    def ok(self) -> bool:
        return (
            self.blanket_is_nontrivial
            and all(name in self.mandatory_sensors for name in self.hidden_deps)
            and self.physical_sensor_contract_ok
        )

    @property
    def proof_of_property(self) -> dict[str, Any]:
        return {
            "E35": "Stigmergic Observability — Markov Blanket for the trace ledger",
            "theorem": (
                "|{s : s is HIDDEN ∧ s ∈ organ_deps}| ≥ 1 "
                "(blanket is non-trivial)"
            ),
            "kind_classes": {k: v.name for k, v in self.kind_classes.items()},
            "observable_count": len(self.observable_kinds),
            "partial_count": len(self.partial_kinds),
            "hidden_dep_count": len(self.hidden_deps),
            "mandatory_sensor_count": len(self.mandatory_sensor_names),
            "blanket_nontrivial": self.blanket_is_nontrivial,
            "hidden_deps": list(self.hidden_deps.keys()),
            "mandatory_sensors": {k: list(v) for k, v in self.mandatory_sensors.items()},
            "observed_kind_counts": dict(self.observed_kind_counts),
            "unknown_kinds": self.unknown_kinds,
            "physical_sensor_contract_ok": self.physical_sensor_contract_ok,
            "physical_observation_count": self.physical_observation_count,
            "physical_sensor_kinds_observed": list(self.physical_sensor_kinds_observed),
            "physical_presence": (
                self.physical_space.physical_presence if self.physical_space else None
            ),
            "presence_gates_ok": (
                self.physical_space.presence_gates_ok if self.physical_space else None
            ),
            "falsifier": (
                "If all organ dependencies were OBSERVABLE, the free-energy "
                "inference layer (Friston 2010) would be vacuous — §8.6 "
                "substrate honesty, RLHS drift detection, and GPS staleness "
                "checks collectively refute this."
            ),
            "friston_reference": "Friston 2010 NRN doi:10.1038/nrn2787",
            "truth_label": "OPERATIONAL",
        }

    def effective_obs_for_dep(self, dep_name: str) -> Obs:
        return effective_hidden_dep_observability(dep_name, physical_space=self.physical_space)

    def summary_lines(self) -> list[str]:
        lines = [
            "E35 Stigmergic Observability (Markov Blanket): OPERATIONAL",
            f"trace kinds classified: {len(self.kind_classes)}",
            f"  OBSERVABLE: {len(self.observable_kinds)} — {', '.join(self.observable_kinds)}",
            f"  PARTIAL:    {len(self.partial_kinds)} — {', '.join(self.partial_kinds)}",
            f"  HIDDEN deps: {len(self.hidden_deps)} — {', '.join(self.hidden_dep_names)}",
            f"mandatory sensors: {len(self.mandatory_sensor_names)}",
            f"physical sensor contract ok: {self.physical_sensor_contract_ok}",
            f"physical observations: {self.physical_observation_count} — {', '.join(self.physical_sensor_kinds_observed) or 'none'}",
            f"unknown observed kinds: {len(self.unknown_kinds)} — {', '.join(self.unknown_kinds) or 'none'}",
            f"blanket_nontrivial: {self.blanket_is_nontrivial}",
            "",
            "hidden organ dependencies:",
        ]
        for name, dep in self.hidden_deps.items():
            lines.append(f"  {name} [{dep['organ']}]: {dep['description'][:70]}...")
        if self.mandatory_sensors:
            lines.append("")
            lines.append("mandatory sensors:")
            for name, sensors in self.mandatory_sensors.items():
                lines.append(f"  {name}: {', '.join(sensors)}")
        return lines


# ── Factory ──────────────────────────────────────────────────────────────────

def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for idx, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            rows.append({"kind": "JSON_PARSE_ERROR", "error": f"line={idx}: {exc}"})
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def observed_kind_counts(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        kind = str(row.get("kind") or row.get("event") or "legacy")
        counts[kind] = counts.get(kind, 0) + 1
    return counts


def effective_hidden_dep_observability(
    dep_name: str,
    *,
    physical_space: "PhysicalSpaceReport | None" = None,
) -> Obs:
    """Return observability class for a hidden organ dependency under E35+ gating.

    When ``requires_physical_sensor`` is True on the dependency, the Markov blanket
    is treated as PARTIAL until `PhysicalSpaceReport.presence_gates_ok` is true
    (camera/mic presence anchor or unified-field segment). This encodes the
    covenant stance: do not pretend carbon-level presence is locked without probes.
    """
    dep = HIDDEN_ORGAN_DEPS.get(dep_name)
    if dep is None:
        return Obs.HIDDEN
    base: Obs = dep["obs"]
    if not dep.get("requires_physical_sensor"):
        return base
    if physical_space is None:
        return Obs.PARTIAL
    if not physical_space.presence_gates_ok:
        return Obs.PARTIAL
    return base


def build_observability_report_from_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    physical_space: "PhysicalSpaceReport | None" = None,
) -> ObservabilityReport:
    row_tuple = tuple(rows)
    if physical_space is None:
        physical_space = build_physical_space_report(row_tuple)
    return ObservabilityReport(
        kind_classes=dict(KIND_OBSERVABILITY),
        hidden_deps=dict(HIDDEN_ORGAN_DEPS),
        physical_space=physical_space,
        mandatory_sensors=dict(MANDATORY_SENSORS),
        observed_kind_counts=observed_kind_counts(row_tuple),
        physical_observation_count=len(physical_space.observations),
        physical_sensor_kinds_observed=physical_space.sensor_kinds,
    )


def build_observability_report() -> ObservabilityReport:
    """Build the canonical Markov blanket report from the static schema."""
    return ObservabilityReport(
        kind_classes=dict(KIND_OBSERVABILITY),
        hidden_deps=dict(HIDDEN_ORGAN_DEPS),
        mandatory_sensors=dict(MANDATORY_SENSORS),
    )


def observability_report() -> ObservabilityReport:
    """Alias for build_observability_report (public API)."""
    return build_observability_report()


def fixture_observability_report(path: Path = _FIXTURE) -> ObservabilityReport:
    return build_observability_report_from_rows(load_jsonl(path))


def _load_json_file(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        row = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return row if isinstance(row, dict) else None


def live_observability_rows(
    *,
    state_dir: Path | None = None,
    limit: int = 300,
    limit_per_ledger: int | None = None,
) -> list[dict[str, Any]]:
    """Read the live E35 evidence window from trace plus physical ledgers."""
    root = Path(state_dir) if state_dir is not None else _STATE
    per_ledger = max(1, int(limit_per_ledger or max(25, limit // max(1, len(_LIVE_JSONL_NAMES)))))
    rows: list[dict[str, Any]] = []
    for name in _LIVE_JSONL_NAMES:
        path = root / name
        for row in load_jsonl(path)[-per_ledger:]:
            annotated = dict(row)
            annotated.setdefault("source_ledger", name)
            rows.append(annotated)
    for name in _LIVE_JSON_NAMES:
        row = _load_json_file(root / name)
        if row is None:
            continue
        annotated = dict(row)
        annotated.setdefault("source_ledger", name)
        if name == "thermal_cortex_state.json":
            annotated.setdefault("kind", "system_thermal")
        elif name == "unified_stigmergic_field_latest.json":
            annotated.setdefault("kind", "UNIFIED_STIGMERGIC_FIELD_V1")
        rows.append(annotated)
    rows.sort(key=lambda r: float(r.get("ts") or r.get("ts_captured") or 0.0))
    return rows[-max(1, int(limit)):]


def live_observability_report(
    *,
    limit: int = 300,
    state_dir: Path | None = None,
    physical_max_age_s: float | None = 7200.0,
    now_ts: float | None = None,
) -> ObservabilityReport:
    rows = live_observability_rows(state_dir=state_dir, limit=limit)
    now = time.time() if now_ts is None else float(now_ts)
    physical_space = build_physical_space_report(
        rows,
        now_ts=now,
        max_age_s=physical_max_age_s,
    )
    return build_observability_report_from_rows(rows, physical_space=physical_space)


if __name__ == "__main__":
    print("\n".join(live_observability_report().summary_lines()))
