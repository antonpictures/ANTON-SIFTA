#!/usr/bin/env python3
"""
System/swarm_field_to_cpg_modulator.py
======================================

Slow stigmergic field -> fast CPG parameter bridge.

The slow field is read from `.sifta_state/organ_field_vector.jsonl`. It changes
the fast oscillators through bounded physics-inspired terms:

  - thermal load lowers oscillator frequency;
  - energy pressure lowers coupling and amplitude;
  - DFA WARN/VETO clamps the fast layer before hardware can move.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from System.jsonl_file_lock import read_text_locked
from System.swarm_edge_receipts import append_chained_receipt

MODULE_VERSION = "2026-05-15.edge-field-cpg-modulator.v1"
FIELD_LEDGER = "organ_field_vector.jsonl"
MODULATION_LEDGER = "fast_cpg_modulation.jsonl"


def _clamp(value: Any, lo: float, hi: float, default: float = 0.0) -> float:
    try:
        out = float(value)
        if not math.isfinite(out):
            return default
        return max(lo, min(hi, out))
    except Exception:
        return default


def _latest_jsonl(path: Path) -> Dict[str, Any]:
    text = read_text_locked(path, encoding="utf-8", errors="replace")
    for line in reversed(text.splitlines()):
        if not line.strip():
            continue
        try:
            row = __import__("json").loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            return row
    return {}


def _payload(row: Dict[str, Any]) -> Dict[str, Any]:
    payload = row.get("payload")
    return payload if isinstance(payload, dict) else row


def _nested_float(payload: Dict[str, Any], keys: Iterable[str], default: float = 0.0) -> float:
    for key in keys:
        if key in payload:
            return _clamp(payload.get(key), 0.0, 1.0, default)
    metabolic_cost = payload.get("metabolic_cost")
    if isinstance(metabolic_cost, dict):
        for key in keys:
            if key in metabolic_cost:
                return _clamp(metabolic_cost.get(key), 0.0, 1.0, default)
    return default


def _derive_dfa_state(payload: Dict[str, Any]) -> str:
    direct = str(payload.get("dfa_state") or "").strip().upper()
    if direct in {"SAFE", "WARN", "VETO"}:
        return direct

    gate = ""
    motor_policy = payload.get("motor_effector_policy")
    if isinstance(motor_policy, dict):
        gate = str(motor_policy.get("effector_gate") or "").strip().upper()
    if gate in {"VETO", "BLOCK", "BLOCKED", "HARDWARE_BLOCKED"}:
        return "VETO"

    homeostasis = str(payload.get("field_homeostasis_state") or "").strip().upper()
    if homeostasis in {"CONSERVE_REPAIR", "REGULATE"}:
        return "WARN"
    return "SAFE"


@dataclass(frozen=True)
class SlowFieldModulation:
    thermal_load: float = 0.0
    energy_pressure: float = 0.0
    dfa_state: str = "SAFE"
    source_trace_id: str = ""
    source_ts: float = 0.0
    source_status: str = "missing"

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CpgModulationResult:
    base_omega: Tuple[float, ...]
    modulated_omega: Tuple[float, ...]
    base_coupling: float
    modulated_coupling: float
    base_amplitude: float
    modulated_amplitude: float
    thermal_factor: float
    energy_factor: float
    dfa_state: str
    modulation: SlowFieldModulation

    def as_dict(self) -> Dict[str, Any]:
        out = asdict(self)
        out["base_omega"] = list(self.base_omega)
        out["modulated_omega"] = list(self.modulated_omega)
        out["modulation"] = self.modulation.as_dict()
        return out


def load_latest_modulation(*, state_dir: Optional[Path] = None) -> SlowFieldModulation:
    root = Path(state_dir) if state_dir is not None else Path(__file__).resolve().parent.parent / ".sifta_state"
    row = _latest_jsonl(root / FIELD_LEDGER)
    if not row:
        return SlowFieldModulation()
    payload = _payload(row)
    thermal = _nested_float(payload, ("thermal_load", "thermal", "heat_pressure"), 0.0)
    energy = _nested_float(payload, ("energy_pressure", "cost_pressure", "pressure"), 0.0)
    return SlowFieldModulation(
        thermal_load=thermal,
        energy_pressure=energy,
        dfa_state=_derive_dfa_state(payload),
        source_trace_id=str(row.get("trace_id") or payload.get("tick_id") or ""),
        source_ts=float(row.get("ts") or payload.get("ts") or 0.0),
        source_status="observed",
    )


def compute_cpg_modulation(
    base_omega: Sequence[float],
    base_coupling: float,
    base_amplitude: float = 1.0,
    *,
    modulation: Optional[SlowFieldModulation] = None,
    state_dir: Optional[Path] = None,
) -> CpgModulationResult:
    m = modulation or load_latest_modulation(state_dir=state_dir)
    base = tuple(float(w) for w in base_omega)
    thermal_factor = max(0.3, 1.0 - 0.6 * _clamp(m.thermal_load, 0.0, 1.0))
    energy_factor = max(0.2, 1.0 - _clamp(m.energy_pressure, 0.0, 1.0))
    dfa_state = str(m.dfa_state or "SAFE").upper()

    if dfa_state == "VETO":
        modulated = tuple(round(w * 0.05, 6) for w in base)
        return CpgModulationResult(
            base_omega=base,
            modulated_omega=modulated,
            base_coupling=float(base_coupling),
            modulated_coupling=0.02,
            base_amplitude=float(base_amplitude),
            modulated_amplitude=0.1,
            thermal_factor=thermal_factor,
            energy_factor=0.05,
            dfa_state=dfa_state,
            modulation=m,
        )

    if dfa_state == "WARN":
        energy_factor *= 0.5

    modulated = tuple(round(w * thermal_factor * energy_factor, 6) for w in base)
    return CpgModulationResult(
        base_omega=base,
        modulated_omega=modulated,
        base_coupling=float(base_coupling),
        modulated_coupling=round(float(base_coupling) * energy_factor, 6),
        base_amplitude=float(base_amplitude),
        modulated_amplitude=round(float(base_amplitude) * energy_factor, 6),
        thermal_factor=round(thermal_factor, 6),
        energy_factor=round(energy_factor, 6),
        dfa_state=dfa_state,
        modulation=m,
    )


def modulate_cpg(
    base_omega: Sequence[float],
    base_coupling: float,
    base_amplitude: float = 1.0,
    *,
    state_dir: Optional[Path] = None,
) -> Tuple[List[float], float, float]:
    result = compute_cpg_modulation(
        base_omega,
        base_coupling,
        base_amplitude,
        state_dir=state_dir,
    )
    return list(result.modulated_omega), result.modulated_coupling, result.modulated_amplitude


def write_modulation_receipt(
    base_omega: Sequence[float],
    base_coupling: float,
    base_amplitude: float = 1.0,
    *,
    state_dir: Optional[Path] = None,
    source: str = "swarm_field_to_cpg_modulator",
) -> Dict[str, Any]:
    result = compute_cpg_modulation(
        base_omega,
        base_coupling,
        base_amplitude,
        state_dir=state_dir,
    )
    return append_chained_receipt(
        state_dir=state_dir,
        ledger_name=MODULATION_LEDGER,
        source=source,
        event_type="FAST_CPG_MODULATION",
        payload={"module_version": MODULE_VERSION, **result.as_dict()},
        status=result.dfa_state.lower(),
        ok=True,
    )


__all__ = [
    "CpgModulationResult",
    "SlowFieldModulation",
    "compute_cpg_modulation",
    "load_latest_modulation",
    "modulate_cpg",
    "write_modulation_receipt",
]


if __name__ == "__main__":
    row = write_modulation_receipt([1.0, 1.1, 1.2, 1.3], 0.35)
    print(__import__("json").dumps(row, indent=2, sort_keys=True))
