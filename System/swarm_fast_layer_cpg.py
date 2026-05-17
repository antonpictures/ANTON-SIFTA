#!/usr/bin/env python3
"""
System/swarm_fast_layer_cpg.py
==============================

Simulation-first fast central-pattern-generator organ for the Edge Species
stack.

This module is intentionally honest about its boundary:

  - it implements the same 1 ms integration step that a Jetson loop would use;
  - it does not claim the host process is scheduled at real-time 1 kHz;
  - motor output goes through swarm_jetson_motor_binding, which only sends real
    PWM when Jetson.GPIO is present and SIFTA_JETSON_MOTOR_ENABLE=1 is set.
"""
from __future__ import annotations

import argparse
import json
import math
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from System.swarm_edge_receipts import append_chained_receipt
from System.swarm_field_to_cpg_modulator import compute_cpg_modulation, write_modulation_receipt
from System.swarm_jetson_motor_binding import send_joint_command

MODULE_VERSION = "2026-05-16.fast-layer-cpg.v1"
CPG_TICK_LEDGER = "fast_layer_cpg_ticks.jsonl"


@dataclass(frozen=True)
class FastCpgConfig:
    joints: Tuple[str, ...] = (
        "j0_shoulder",
        "j1_elbow",
        "j2_wrist",
        "j3_gripper",
    )
    base_omega: Tuple[float, ...] = (1.0, 1.1, 1.2, 1.3)
    base_coupling: float = 0.35
    base_amplitude: float = 0.60
    phase_lag: float = math.pi / 4.0
    dt_s: float = 0.001
    ledger_name: str = CPG_TICK_LEDGER


@dataclass(frozen=True)
class FastCpgState:
    phases: Tuple[float, ...]
    tick_index: int = 0

    @classmethod
    def initial(cls, joint_count: int) -> "FastCpgState":
        if joint_count <= 0:
            raise ValueError("joint_count must be positive")
        return cls(
            phases=tuple((2.0 * math.pi * i) / joint_count for i in range(joint_count)),
            tick_index=0,
        )

    def as_dict(self) -> Dict[str, Any]:
        out = asdict(self)
        out["phases"] = list(self.phases)
        return out


def _validate_config(cfg: FastCpgConfig) -> None:
    if not cfg.joints:
        raise ValueError("FastCpgConfig.joints must not be empty")
    if len(cfg.joints) != len(cfg.base_omega):
        raise ValueError("FastCpgConfig.joints and base_omega must have the same length")
    if cfg.dt_s <= 0:
        raise ValueError("FastCpgConfig.dt_s must be positive")
    if cfg.base_amplitude < 0:
        raise ValueError("FastCpgConfig.base_amplitude must be non-negative")


def _validate_state(state: FastCpgState, joint_count: int) -> None:
    if len(state.phases) != joint_count:
        raise ValueError("FastCpgState phase count must match configured joint count")
    if state.tick_index < 0:
        raise ValueError("FastCpgState.tick_index must be non-negative")


def _kuramoto_step(phases: Sequence[float], omega: Sequence[float], coupling: float, phase_lag: float, dt_s: float) -> Tuple[float, ...]:
    n = len(phases)
    next_phases: List[float] = []
    for i, phase in enumerate(phases):
        previous_phase = phases[(i - 1) % n]
        next_phase = phases[(i + 1) % n]
        coupling_term = 0.5 * coupling * (
            math.sin(previous_phase - phase - phase_lag)
            + math.sin(next_phase - phase + phase_lag)
        )
        next_phases.append((phase + float(omega[i]) * dt_s + coupling_term * dt_s) % (2.0 * math.pi))
    return tuple(next_phases)


def step_cpg(
    *,
    state: Optional[FastCpgState] = None,
    cfg: Optional[FastCpgConfig] = None,
    state_dir: Optional[Path] = None,
    drive_motors: bool = True,
    source: str = "swarm_fast_layer_cpg",
) -> Dict[str, Any]:
    """Advance the CPG one integration step and emit chained receipts."""
    cfg = cfg or FastCpgConfig()
    _validate_config(cfg)
    current = state or FastCpgState.initial(len(cfg.joints))
    _validate_state(current, len(cfg.joints))

    modulation = compute_cpg_modulation(
        cfg.base_omega,
        cfg.base_coupling,
        cfg.base_amplitude,
        state_dir=state_dir,
    )
    modulation_receipt = write_modulation_receipt(
        cfg.base_omega,
        cfg.base_coupling,
        cfg.base_amplitude,
        state_dir=state_dir,
        source=source,
    )

    next_phases = _kuramoto_step(
        current.phases,
        modulation.modulated_omega,
        modulation.modulated_coupling,
        cfg.phase_lag,
        cfg.dt_s,
    )
    outputs = tuple(round(modulation.modulated_amplitude * math.sin(phase), 6) for phase in next_phases)
    next_state = FastCpgState(phases=next_phases, tick_index=current.tick_index + 1)

    tick_payload = {
        "module_version": MODULE_VERSION,
        "tick_index": next_state.tick_index,
        "dt_s": cfg.dt_s,
        "real_time_claim": False,
        "truth_note": "This is a deterministic integration step, not a measured host scheduling guarantee.",
        "joints": list(cfg.joints),
        "phases": [round(value, 9) for value in next_phases],
        "outputs": {joint: value for joint, value in zip(cfg.joints, outputs)},
        "drive_motors": bool(drive_motors),
        "modulation": modulation.as_dict(),
        "modulation_trace_id": modulation_receipt.get("trace_id", ""),
        "modulation_receipt_hash": modulation_receipt.get("receipt_hash", ""),
    }
    tick_row = append_chained_receipt(
        state_dir=state_dir,
        ledger_name=cfg.ledger_name,
        source=source,
        event_type="FAST_LAYER_CPG_TICK",
        status=modulation.dfa_state.lower(),
        ok=True,
        payload=tick_payload,
    )

    motor_rows: List[Dict[str, Any]] = []
    if drive_motors:
        for joint, output in zip(cfg.joints, outputs):
            motor_rows.append(
                send_joint_command(
                    joint,
                    output,
                    state_dir=state_dir,
                    source=source,
                )
            )

    return {
        "ok": True,
        "state": next_state,
        "tick": tick_row,
        "motor_rows": motor_rows,
        "modulation_receipt": modulation_receipt,
    }


def run_cpg_steps(
    *,
    steps: int = 10,
    cfg: Optional[FastCpgConfig] = None,
    initial_state: Optional[FastCpgState] = None,
    state_dir: Optional[Path] = None,
    drive_motors: bool = True,
    sleep_s: float = 0.0,
) -> Dict[str, Any]:
    if steps < 0:
        raise ValueError("steps must be non-negative")
    cfg = cfg or FastCpgConfig()
    _validate_config(cfg)
    state = initial_state or FastCpgState.initial(len(cfg.joints))
    _validate_state(state, len(cfg.joints))

    step_reports: List[Dict[str, Any]] = []
    started = time.time()
    for _ in range(steps):
        result = step_cpg(
            state=state,
            cfg=cfg,
            state_dir=state_dir,
            drive_motors=drive_motors,
        )
        state = result["state"]
        step_reports.append(
            {
                "tick": result["tick"],
                "motor_rows": result["motor_rows"],
                "modulation_receipt": result["modulation_receipt"],
            }
        )
        if sleep_s > 0:
            time.sleep(sleep_s)

    elapsed_s = time.time() - started
    return {
        "ok": True,
        "module_version": MODULE_VERSION,
        "steps_requested": steps,
        "steps_completed": len(step_reports),
        "drive_motors": bool(drive_motors),
        "configured_dt_s": cfg.dt_s,
        "elapsed_s": round(elapsed_s, 6),
        "real_time_claim": False,
        "final_state": state.as_dict(),
        "steps": step_reports,
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run the SIFTA fast-layer CPG in simulation-safe mode.")
    parser.add_argument("--steps", type=int, default=10)
    parser.add_argument("--sleep-s", type=float, default=0.0)
    parser.add_argument("--no-motors", action="store_true", help="Emit CPG ticks but skip motor-binding receipts.")
    args = parser.parse_args(list(argv) if argv is not None else None)

    report = run_cpg_steps(
        steps=args.steps,
        drive_motors=not args.no_motors,
        sleep_s=args.sleep_s,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


__all__ = [
    "CPG_TICK_LEDGER",
    "FastCpgConfig",
    "FastCpgState",
    "run_cpg_steps",
    "step_cpg",
]


if __name__ == "__main__":
    raise SystemExit(main())
