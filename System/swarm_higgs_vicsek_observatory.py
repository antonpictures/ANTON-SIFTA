#!/usr/bin/env python3
"""Combined Higgs/Vicsek payload for the Physics Observatory.

This module is deliberately Qt-free. The UI can render its payload, and tests
can verify the science/truth labels without importing PyQt6 or matplotlib.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Sequence

from System.swarm_active_matter_field import (
    ACTIVE_MATTER_TRUTH_GUARD,
    render_scan_ascii,
    vicsek_noise_scan,
)
from System.swarm_higgs_stigmergy_field import (
    TRUTH_BOUNDARY as HIGGS_TRUTH_BOUNDARY,
    TRUTH_LABEL as HIGGS_TRUTH_LABEL,
    HiggsFieldConfig,
    render_ascii as render_higgs_ascii,
    run_higgs_stigmergy_demo,
)

TRUTH_LABEL = "PHYSICS_OBSERVATORY_ENGINE_C_HIGGS_VICSEK_V1"
LEDGER_NAME = "physics_observatory_engine_c.jsonl"
TRUTH_BOUNDARY = (
    "Classical SIFTA analogues only: Vicsek flocking and scalar-field "
    "symmetry breaking. No OBSERVED Higgs bosons, no collider result, "
    "no Yang-Mills proof on this node."
)
DEFAULT_NOISES = (0.1, 1.2, 2.4, 3.6, 4.8, 6.0)


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _state_dir(state_root: str | Path | None = None) -> Path:
    if state_root is None:
        env = os.environ.get("SIFTA_STATE_ROOT")
        if env:
            return Path(env)
        return _repo_root() / ".sifta_state"
    p = Path(state_root)
    if (p / "System").exists() and (p / ".sifta_state").exists():
        return p / ".sifta_state"
    return p


def build_engine_c_payload(
    *,
    noises: Sequence[float] = DEFAULT_NOISES,
    vicsek_particles: int = 120,
    vicsek_burn_in_steps: int = 90,
    vicsek_average_steps: int = 45,
    seed: int = 20260513,
    higgs_steps: int = 160,
    write_higgs_receipt: bool = False,
) -> dict[str, Any]:
    """Run the two canonical tournament engines and return one payload."""
    scan = vicsek_noise_scan(
        noises=noises,
        n_particles=vicsek_particles,
        box_size=5.0,
        burn_in_steps=vicsek_burn_in_steps,
        average_over_steps=vicsek_average_steps,
        seed=seed,
    )
    higgs = run_higgs_stigmergy_demo(
        config=HiggsFieldConfig(seed=13, width=24, height=16),
        steps=higgs_steps,
        write=write_higgs_receipt,
    )
    scan_d = scan.as_dict()
    crit = scan.critical_noise_estimate()
    low_phi = float(scan.polar_orders[0]) if scan.polar_orders else 0.0
    high_phi = float(scan.polar_orders[-1]) if scan.polar_orders else 0.0
    strongest = max(higgs["swimmers"], key=lambda s: float(s["effective_mass"]))
    weakest = min(higgs["swimmers"], key=lambda s: float(s["effective_mass"]))
    payload = {
        "truth_label": TRUTH_LABEL,
        "truth_boundary": TRUTH_BOUNDARY,
        "simulated": True,
        "no_particle_physics_claim": True,
        "vicsek": {
            "truth_guard": ACTIVE_MATTER_TRUTH_GUARD,
            "scan": scan_d,
            "critical_noise_estimate": crit,
            "low_noise_phi": round(low_phi, 6),
            "high_noise_phi": round(high_phi, 6),
            "order_drop": round(low_phi - high_phi, 6),
            "ascii": render_scan_ascii(scan, width=36),
        },
        "higgs": {
            "truth_label": HIGGS_TRUTH_LABEL,
            "truth_boundary": HIGGS_TRUTH_BOUNDARY,
            "result": higgs,
            "ascii": render_higgs_ascii(higgs),
        },
        "summary": {
            "vicsek_order_drop": round(low_phi - high_phi, 6),
            "higgs_order_parameter": higgs["order_parameter"],
            "higgs_mass_span": higgs["mass_span"],
            "weakest_swimmer_mass": weakest["effective_mass"],
            "strongest_swimmer_mass": strongest["effective_mass"],
        },
    }
    return payload


def write_engine_c_receipt(
    payload: dict[str, Any],
    *,
    state_root: str | Path | None = None,
) -> dict[str, Any]:
    state = _state_dir(state_root)
    state.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    row = {
        "ts": time.time(),
        "kind": "PHYSICS_OBSERVATORY_ENGINE_C",
        "trace_id": str(uuid.uuid4()),
        "truth_label": TRUTH_LABEL,
        "truth_boundary": TRUTH_BOUNDARY,
        "sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        "payload": payload,
    }
    with (state / LEDGER_NAME).open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")
    return {k: v for k, v in row.items() if k != "payload"}


def run_engine_c(
    *,
    state_root: str | Path | None = None,
    write_receipt: bool = True,
    **kwargs: Any,
) -> dict[str, Any]:
    payload = build_engine_c_payload(**kwargs)
    if write_receipt:
        payload["receipt"] = write_engine_c_receipt(payload, state_root=state_root)
    return payload


def render_engine_c_summary(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    crit = payload["vicsek"]["critical_noise_estimate"]
    crit_s = "n/a" if crit is None else f"{crit:.3f}"
    return "\n\n".join(
        [
            "Engine C — Swarm Field / Higgs-Vicsek",
            f"truth: {payload['truth_label']}",
            f"boundary: {payload['truth_boundary']}",
            (
                "Vicsek: "
                f"φ drop={summary['vicsek_order_drop']:.3f}, "
                f"ηc≈{crit_s}"
            ),
            (
                "Higgs analogue: "
                f"order={summary['higgs_order_parameter']:.3f}, "
                f"mass span={summary['higgs_mass_span']:.3f}, "
                f"strongest mass={summary['strongest_swimmer_mass']:.3f}"
            ),
            payload["vicsek"]["ascii"],
            payload["higgs"]["ascii"],
        ]
    )
