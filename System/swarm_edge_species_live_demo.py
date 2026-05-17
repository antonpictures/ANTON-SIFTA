#!/usr/bin/env python3
"""
System/swarm_edge_species_live_demo.py
======================================

A deterministic M5-safe live demo for the Edge Species stack.

It writes slow field states, computes fast CPG modulation, emits simulated
motor commands, then verifies the unified hash chain. On Jetson, the same
motor binding can actuate hardware only when explicitly armed.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from System.swarm_edge_receipts import append_chained_receipt
from System.swarm_edge_unified_verifier import verify_unified_chain
from System.swarm_fast_layer_cpg import run_cpg_steps
from System.swarm_field_to_cpg_modulator import write_modulation_receipt
from System.swarm_jetson_motor_binding import send_joint_command, setup


def _write_field_state(
    *,
    state_dir: Optional[Path],
    label: str,
    thermal_load: float,
    energy_pressure: float,
    dfa_state: str,
) -> Dict[str, Any]:
    return append_chained_receipt(
        state_dir=state_dir,
        ledger_name="organ_field_vector.jsonl",
        source="swarm_edge_species_live_demo",
        event_type="EDGE_DEMO_FIELD_STATE",
        status=dfa_state.lower(),
        ok=True,
        payload={
            "label": label,
            "thermal_load": thermal_load,
            "energy_pressure": energy_pressure,
            "dfa_state": dfa_state,
            "field_homeostasis_state": "CONSERVE_REPAIR" if dfa_state == "WARN" else "VIABLE",
            "motor_effector_policy": {
                "effector_gate": "VETO" if dfa_state == "VETO" else "LEDGER_ONLY",
            },
        },
    )


def run_demo(*, state_dir: Optional[Path] = None, sleep_s: float = 0.0) -> Dict[str, Any]:
    root = Path(state_dir) if state_dir is not None else Path(__file__).resolve().parent.parent / ".sifta_state"
    root.mkdir(parents=True, exist_ok=True)
    steps: List[Dict[str, Any]] = []

    steps.append({"name": "setup", "receipt": setup(state_dir=root)})
    script = [
        ("baseline", 0.0, 0.0, "SAFE", 0.40),
        ("thermal_pulse", 0.65, 0.25, "WARN", 0.40),
        ("stacked_damage", 0.90, 0.85, "VETO", 0.40),
        ("autonomous_recovery", 0.10, 0.10, "SAFE", 0.25),
    ]
    for label, thermal, pressure, dfa, motor_value in script:
        field = _write_field_state(
            state_dir=root,
            label=label,
            thermal_load=thermal,
            energy_pressure=pressure,
            dfa_state=dfa,
        )
        modulation = write_modulation_receipt([1.0, 1.1, 1.2, 1.3], 0.35, state_dir=root)
        cpg = run_cpg_steps(steps=1, state_dir=root, drive_motors=True)
        motor = send_joint_command("j2_wrist", motor_value, state_dir=root)
        steps.append({"name": label, "field": field, "modulation": modulation, "cpg": cpg, "motor": motor})
        if sleep_s > 0:
            time.sleep(sleep_s)

    verification = verify_unified_chain(state_dir=root, write_receipt=True)
    return {
        "ok": bool(verification.get("ok")),
        "truth_label": "OPERATIONAL" if verification.get("ok") else "BROKEN",
        "steps": steps,
        "verification": verification,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Edge Species simulated live demo.")
    parser.add_argument(
        "--state-dir",
        default="",
        help="Optional state directory for demo ledgers; defaults to repo .sifta_state.",
    )
    parser.add_argument(
        "--sleep-s",
        type=float,
        default=0.0,
        help="Optional pause between scripted field states.",
    )
    args = parser.parse_args()
    report = run_demo(
        state_dir=Path(args.state_dir) if args.state_dir else None,
        sleep_s=max(0.0, float(args.sleep_s)),
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
