"""Publish five canonical organ vitals + staleness reflex (r1021 C5)."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List

_FIVE_VITALS = (
    ("heart", "swarm_hardware_heart"),
    ("cortex_mouth", "sifta_talk_to_alice_widget"),
    ("effector_gate", "swarm_effector_gate"),
    ("organ_registry", "swarm_canonical_organ_registry"),
    ("self_improvement", "swarm_self_improvement_loop"),
)


def publish_five_vitals(*, state_dir: Path | str | None = None) -> List[Dict[str, Any]]:
    from System.swarm_canonical_organ_registry import publish_organ_vital, latest_organ_field

    sd = Path(state_dir) if state_dir else Path(__file__).resolve().parents[1] / ".sifta_state"
    if sd.name != ".sifta_state":
        sd = sd / ".sifta_state"
    repo = Path(__file__).resolve().parents[1]
    published: List[Dict[str, Any]] = []
    for organ_id, module_stem in _FIVE_VITALS:
        mod_path = repo / "System" / f"{module_stem}.py"
        app_path = repo / "Applications" / f"{module_stem}.py"
        exists = mod_path.exists() or app_path.exists()
        health = 0.85 if exists else 0.2
        load = 0.3 if exists else 0.9
        signal = f"module_present={exists}"
        row = publish_organ_vital(
            organ=organ_id,
            health=health,
            load=load,
            top_signal=signal,
            state_dir=sd,
        )
        published.append(row)
    # staleness reflex: decay note on stale vitals
    field = latest_organ_field(state_dir=sd, stale_after_s=120.0)
    stale = [r for r in field if float(r.get("staleness_s") or 0) > 120.0]
    if stale:
        publish_organ_vital(
            organ="organ_field_reflex",
            health=0.5,
            load=min(1.0, len(stale) / 10.0),
            top_signal=f"stale_organs={len(stale)}",
            state_dir=sd,
        )
    return published