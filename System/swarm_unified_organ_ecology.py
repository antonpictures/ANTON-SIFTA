#!/usr/bin/env python3
"""Unified organ ecology mesh.

This layer sits on top of ``organ_field_vector.jsonl`` and makes the field
explicit at organ/swimmer resolution:

- every swimmer has a home organ and a role inside that organ;
- every organ gets incoming/outgoing communication edges;
- each organ gets a health action and a lightweight STGM profitability signal.

It does not replace the body-brain loop. It consumes the high-dimensional field
receipt that loop already writes, then emits an append-only ecology receipt.
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Any, Mapping

from System.jsonl_file_lock import append_line_locked

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
LEDGER_NAME = "organ_ecology_mesh.jsonl"
LATEST_NAME = "organ_ecology_mesh_latest.json"
SCHEMA = "SIFTA_UNIFIED_ORGAN_ECOLOGY_V1"
KIND = "UNIFIED_ORGAN_ECOLOGY_MESH"


def _payload(row: Mapping[str, Any]) -> Mapping[str, Any]:
    value = row.get("payload")
    return value if isinstance(value, Mapping) else row


def _clamp01(value: Any, default: float = 0.0) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _organ_name_for_endpoint(endpoint: Any, organ_names: set[str]) -> str:
    """Map an edge endpoint string to a known organ when possible."""
    text = str(endpoint or "").strip()
    folded = text.casefold()
    for organ in organ_names:
        if folded == organ.casefold():
            return organ
    aliases = {
        "motor_bus": "octopus",
        "octopus": "octopus",
        "cuttlefish": "cuttlefish",
        "electric_field": "electric",
        "electric": "electric",
        "waggle": "honeybee",
        "honeybee": "honeybee",
        "td_receipts": "td_learner",
        "td_learner": "td_learner",
        "dopamine": "dopamine",
        "hippocampus": "hippocampus",
        "basal_ganglia": "bg_selector",
        "bg_selector": "bg_selector",
        "sensor_gate": "sensor_gate",
        "metabolic": "metabolic",
        "body_brain_tick": "metabolic",
        "field_homeostasis": "field",
        "field_memory": "field",
        "organ_field": "field",
        "truth_continuity": "td_learner",
        "reflex": "reflex",
    }
    for needle, organ in aliases.items():
        if needle in folded and organ in organ_names:
            return organ
    return ""


def _role_for_swimmer(index: int, organ: str, health: float) -> str:
    if health < 0.35:
        return "repair"
    roles = ("sense", "relay", "homeostasis", "memory", "profit")
    return roles[index % len(roles)]


def _profitability(*, health: float, swimmers: int, cost_pressure: float) -> dict[str, Any]:
    """Return a bounded STGM pressure estimate for one organ."""
    swimmers = max(1, int(swimmers))
    mint_potential = health * swimmers * 0.05
    upkeep_cost = (swimmers ** 0.75) * 0.001 * (1.0 + cost_pressure)
    surplus = mint_potential - upkeep_cost
    efficiency = surplus / max(upkeep_cost, 1e-9)
    return {
        "mint_potential_stgm": round(mint_potential, 6),
        "upkeep_cost_stgm": round(upkeep_cost, 6),
        "surplus_stgm": round(surplus, 6),
        "efficiency": round(max(-1.0, min(10.0, efficiency)), 6),
        "profitable": surplus >= 0.0,
    }


def _organ_action(*, health: float, out_degree: int, in_degree: int, cost_pressure: float, profitable: bool) -> str:
    if health <= 0.0:
        return "discover_source"
    if health < 0.35:
        return "repair"
    if not profitable or cost_pressure > 0.80:
        return "conserve"
    if health > 0.85 and (out_degree + in_degree) > 0 and cost_pressure < 0.65:
        return "grow"
    return "maintain"


def build_organ_ecology_mesh(
    field_row: Mapping[str, Any],
    *,
    state_dir: Path | str = _STATE,
    now: float | None = None,
) -> dict[str, Any]:
    """Build an organ/swimmer ecology receipt from one organ-field row."""
    payload = _payload(field_row)
    now_ts = float(now if now is not None else time.time())
    raw_nodes = payload.get("organ_nodes") or []
    organ_nodes = [dict(n) for n in raw_nodes if isinstance(n, Mapping)]
    if not organ_nodes:
        organ_health = payload.get("organ_health") if isinstance(payload.get("organ_health"), Mapping) else {}
        organ_nodes = [
            {"organ": str(k), "health": _clamp01(v), "swimmer_count": 1}
            for k, v in organ_health.items()
        ]

    organ_names = {str(n.get("organ") or "") for n in organ_nodes if n.get("organ")}
    cost_pressure = _clamp01(payload.get("cost_pressure", 0.0))
    field_completeness = _clamp01(payload.get("field_completeness", 0.0))
    coupling_edges = [dict(e) for e in payload.get("coupling_edges", []) if isinstance(e, Mapping)]

    incoming: dict[str, list[dict[str, Any]]] = {name: [] for name in organ_names}
    outgoing: dict[str, list[dict[str, Any]]] = {name: [] for name in organ_names}
    normalized_edges: list[dict[str, Any]] = []
    for edge in coupling_edges:
        src_organ = _organ_name_for_endpoint(edge.get("source"), organ_names)
        dst_organ = _organ_name_for_endpoint(edge.get("target"), organ_names)
        if src_organ or dst_organ:
            norm = {
                "source": str(edge.get("source") or ""),
                "target": str(edge.get("target") or ""),
                "source_organ": src_organ,
                "target_organ": dst_organ,
                "variables": list(edge.get("variables") or [])[:8],
            }
            normalized_edges.append(norm)
            if src_organ:
                outgoing.setdefault(src_organ, []).append(norm)
            if dst_organ:
                incoming.setdefault(dst_organ, []).append(norm)

    raw_swimmers = [
        dict(s)
        for s in payload.get("swimmer_registry", [])
        if isinstance(s, Mapping) and s.get("organ")
    ]
    swimmers_by_organ: dict[str, list[dict[str, Any]]] = {name: [] for name in organ_names}
    for swimmer in raw_swimmers:
        organ = str(swimmer.get("organ") or "")
        if organ in swimmers_by_organ:
            swimmers_by_organ[organ].append(swimmer)

    ecology_nodes: list[dict[str, Any]] = []
    swimmer_assignments: list[dict[str, Any]] = []
    for node in sorted(organ_nodes, key=lambda n: str(n.get("organ") or "")):
        organ = str(node.get("organ") or "")
        if not organ:
            continue
        health = _clamp01(node.get("health", 0.0))
        swimmer_count = int(node.get("swimmer_count") or len(swimmers_by_organ.get(organ, [])) or 1)
        profit = _profitability(health=health, swimmers=swimmer_count, cost_pressure=cost_pressure)
        out_edges = outgoing.get(organ, [])
        in_edges = incoming.get(organ, [])
        action = _organ_action(
            health=health,
            out_degree=len(out_edges),
            in_degree=len(in_edges),
            cost_pressure=cost_pressure,
            profitable=bool(profit["profitable"]),
        )

        local_swimmers = swimmers_by_organ.get(organ) or [
            {"swimmer_id": f"{organ}:{idx}", "organ": organ, "index": idx}
            for idx in range(swimmer_count)
        ]
        swimmer_ids = []
        for idx, swimmer in enumerate(local_swimmers[:swimmer_count]):
            swimmer_id = str(swimmer.get("swimmer_id") or f"{organ}:{idx}")
            swimmer_ids.append(swimmer_id)
            swimmer_assignments.append(
                {
                    "swimmer_id": swimmer_id,
                    "home_organ": organ,
                    "index": int(swimmer.get("index", idx) or idx),
                    "role": _role_for_swimmer(idx, organ, health),
                    "organ_health": round(health, 4),
                    "organ_action": action,
                    "knows_organ": True,
                    "communication_targets": sorted(
                        {e["target_organ"] for e in out_edges if e.get("target_organ")}
                    ),
                    "stgm_surplus": profit["surplus_stgm"],
                }
            )

        ecology_nodes.append(
            {
                "organ": organ,
                "health": round(health, 4),
                "source": node.get("source", ""),
                "resolution": node.get("resolution", ""),
                "swimmer_count": swimmer_count,
                "swimmer_ids": swimmer_ids,
                "incoming_degree": len(in_edges),
                "outgoing_degree": len(out_edges),
                "communication_targets": sorted(
                    {e["target_organ"] for e in out_edges if e.get("target_organ")}
                ),
                "communication_sources": sorted(
                    {e["source_organ"] for e in in_edges if e.get("source_organ")}
                ),
                "stgm_profitability": profit,
                "health_action": action,
            }
        )

    total_surplus = sum(
        _safe_float(node["stgm_profitability"]["surplus_stgm"])
        for node in ecology_nodes
    )
    profitable_organs = sum(1 for node in ecology_nodes if node["stgm_profitability"]["profitable"])
    connected_organs = sum(
        1 for node in ecology_nodes if node["incoming_degree"] + node["outgoing_degree"] > 0
    )
    weak_organs = [node["organ"] for node in ecology_nodes if node["health_action"] in {"repair", "discover_source"}]

    row = {
        "ts": now_ts,
        "schema": SCHEMA,
        "kind": KIND,
        "source": "swarm_unified_organ_ecology",
        "truth_label": "OPERATIONAL",
        "field_tick_id": payload.get("tick_id") or field_row.get("tick_id") or "",
        "organ_count": len(ecology_nodes),
        "connected_organ_count": connected_organs,
        "swimmer_count": len(swimmer_assignments),
        "communication_edge_count": len(normalized_edges),
        "field_completeness": round(field_completeness, 6),
        "cost_pressure": round(cost_pressure, 6),
        "profitable_organ_count": profitable_organs,
        "total_surplus_stgm": round(total_surplus, 6),
        "weak_organs": weak_organs,
        "organ_nodes": ecology_nodes,
        "swimmer_assignments": swimmer_assignments,
        "communication_edges": normalized_edges,
        "source_ledgers": ["organ_field_vector.jsonl"],
    }
    return row


def append_organ_ecology_from_field(
    field_row: Mapping[str, Any],
    *,
    state_dir: Path | str = _STATE,
    now: float | None = None,
) -> dict[str, Any]:
    """Append one ecology mesh row and update the latest snapshot."""
    root = Path(state_dir)
    root.mkdir(parents=True, exist_ok=True)
    row = build_organ_ecology_mesh(field_row, state_dir=root, now=now)
    append_line_locked(root / LEDGER_NAME, json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    try:
        (root / LATEST_NAME).write_text(
            json.dumps(row, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    except OSError:
        pass
    return row


def latest_organ_ecology(*, state_dir: Path | str = _STATE) -> dict[str, Any]:
    path = Path(state_dir) / LATEST_NAME
    try:
        row = json.loads(path.read_text(encoding="utf-8"))
        return row if isinstance(row, dict) else {}
    except Exception:
        return {}


def format_organ_ecology_for_prompt(*, state_dir: Path | str = _STATE) -> str:
    row = latest_organ_ecology(state_dir=state_dir)
    if not row:
        return ""
    return "\n".join(
        [
            "### UNIFIED ORGAN ECOLOGY",
            f"- schema={row.get('schema')}; organs={row.get('connected_organ_count')}/{row.get('organ_count')}; swimmers={row.get('swimmer_count')}",
            f"- communication_edges={row.get('communication_edge_count')}; profitable_organs={row.get('profitable_organ_count')}; total_surplus_stgm={row.get('total_surplus_stgm')}",
            f"- weak_organs={', '.join(row.get('weak_organs') or []) or 'none'}",
            "- Instruction: each swimmer acts from its home_organ, shares edge signals with coupled organs, and chooses repair/conserve/maintain/grow from health plus STGM pressure.",
        ]
    )


if __name__ == "__main__":
    field_path = _STATE / "organ_field_vector.jsonl"
    try:
        line = field_path.read_text(encoding="utf-8").strip().splitlines()[-1]
        field = json.loads(line)
    except Exception:
        field = {"payload": {"organ_nodes": [], "swimmer_registry": [], "coupling_edges": []}}
    print(json.dumps(append_organ_ecology_from_field(field), indent=2, sort_keys=True))
