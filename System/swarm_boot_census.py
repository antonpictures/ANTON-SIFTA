#!/usr/bin/env python3
"""
Boot-time SIFTA census.

The boot launcher used to print a single `len(ORGAN_DEFS)` value. That is
accurate only for the Body Monitor panel, but it hides the wider runtime
surface: identity probes, high-dimensional field rows, connected organs, and
swimmers. Keep those lanes explicit so the boot banner cannot imply one stale
"organ" count.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, Optional


_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"


def _last_jsonl_payload(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        for line in reversed(path.read_text(encoding="utf-8").splitlines()):
            if not line.strip():
                continue
            row = json.loads(line)
            payload = row.get("payload")
            return payload if isinstance(payload, dict) else row
    except Exception:
        return {}
    return {}


def _identity_probe_counts() -> Dict[str, int]:
    try:
        from System.swarm_composite_identity import current_identity, invalidate_cache

        invalidate_cache()
        snap = current_identity(cache_ttl_s=0)
        present = len(getattr(snap, "organs_present", []) or [])
        silent = len(getattr(snap, "organs_silent", []) or [])
        return {
            "identity_present": present,
            "identity_silent": silent,
            "identity_total": present + silent,
        }
    except Exception:
        return {
            "identity_present": 0,
            "identity_silent": 0,
            "identity_total": 0,
        }


def _body_monitor_counts(*, probe_body: bool) -> Dict[str, int]:
    try:
        from System.swarm_body_monitor import (
            ORGAN_DEFS,
            TRUTH_BROKEN,
            TRUTH_DEMO,
            TRUTH_REAL,
            TRUTH_UNKNOWN,
        )

        out = {
            "body_declared_organs": len(ORGAN_DEFS),
            "body_real_organs": 0,
            "body_demo_organs": 0,
            "body_broken_organs": 0,
            "body_unknown_organs": 0,
        }
        if not probe_body:
            return out

        from System.swarm_body_monitor import OrganEngine

        state = OrganEngine().tick_all()
        counts = state.get("truth_counts") or {}
        out.update(
            {
                "body_real_organs": int(counts.get(TRUTH_REAL, 0) or 0),
                "body_demo_organs": int(counts.get(TRUTH_DEMO, 0) or 0),
                "body_broken_organs": int(counts.get(TRUTH_BROKEN, 0) or 0),
                "body_unknown_organs": int(counts.get(TRUTH_UNKNOWN, 0) or 0),
            }
        )
        return out
    except Exception:
        return {
            "body_declared_organs": 0,
            "body_real_organs": 0,
            "body_demo_organs": 0,
            "body_broken_organs": 0,
            "body_unknown_organs": 0,
        }


def boot_census(
    *,
    state_dir: Optional[Path] = None,
    probe_body: bool = True,
    probe_identity: bool = True,
) -> Dict[str, Any]:
    state = Path(state_dir) if state_dir is not None else _STATE
    field = _last_jsonl_payload(state / "organ_field_vector.jsonl")
    out: Dict[str, Any] = {}
    out.update(_body_monitor_counts(probe_body=probe_body))
    out.update(
        _identity_probe_counts()
        if probe_identity
        else {"identity_present": 0, "identity_silent": 0, "identity_total": 0}
    )
    out.update(
        {
            "field_declared_organs": int(field.get("declared_organ_count", 0) or 0),
            "field_connected_organs": int(field.get("connected_organ_count", 0) or 0),
            "field_dimensions": int(field.get("dimension_count", 0) or 0),
            "field_swimmers": int(field.get("swimmer_count", 0) or 0),
            "field_unknown_vectors": int(field.get("unknown_vector_count", 0) or 0),
            "field_coupling_edges": int(field.get("coupling_edge_count", 0) or 0),
            "field_completeness": float(field.get("field_completeness", 0.0) or 0.0),
        }
    )
    return out


def _first_nonzero(values: Iterable[int]) -> int:
    for value in values:
        if value:
            return int(value)
    return 0


def boot_census_lines(census: Optional[Dict[str, Any]] = None) -> list[str]:
    c = census or boot_census()
    real = _first_nonzero(
        [
            int(c.get("body_real_organs", 0) or 0),
            int(c.get("field_connected_organs", 0) or 0),
            int(c.get("body_declared_organs", 0) or 0),
        ]
    )
    demo = int(c.get("body_demo_organs", 0) or 0)
    broken = int(c.get("body_broken_organs", 0) or 0)
    unknown = int(c.get("body_unknown_organs", 0) or 0)
    identity_total = int(c.get("identity_total", 0) or 0)
    identity_present = int(c.get("identity_present", 0) or 0)
    dims = int(c.get("field_dimensions", 0) or 0)
    swimmers = int(c.get("field_swimmers", 0) or 0)
    edges = int(c.get("field_coupling_edges", 0) or 0)
    completeness = float(c.get("field_completeness", 0.0) or 0.0)

    # BOOT: 🐝 on OS line (palette os_line); 🐜 on this organ census row (stigmergy).
    lines = [
        f"🐜  {real} REAL body organs  |  DEMO {demo}  BROKEN {broken}  UNKNOWN {unknown}",
    ]
    if identity_total:
        lines.append(f"🧬  {identity_total} identity probes  |  {identity_present} present now")
    if dims or swimmers or edges:
        lines.append(
            f"🌊  {dims} field dims  |  {swimmers} swimmers  |  {edges} coupling edges"
        )
    if completeness:
        lines.append(f"📈  field completeness {completeness:.3f}  |  Body Panel live")
    else:
        lines.append("📈  Body Panel live")
    return lines


def _active_os_line() -> str:
    env_line = os.getenv("SIFTA_BOOT_OS_LINE")
    if env_line:
        return env_line
    try:
        from System.sifta_desktop_themes import active_palette

        return str(active_palette().os_line)
    except Exception:
        return "🐝 SIFTA BeeSon OS v8.0"


def render_boot_banner(os_line: Optional[str] = None) -> str:
    os_line = os_line or _active_os_line()
    lines = [f"{os_line}  —  BOOT", *boot_census_lines()]
    width = max(58, *(len(line) + 4 for line in lines))
    top = "  ╔" + ("═" * width) + "╗"
    bottom = "  ╚" + ("═" * width) + "╝"
    body = [top]
    for line in lines:
        body.append(f"  ║  {line:<{width - 2}}║")
    body.append(bottom)
    return "\n".join(body)


def main() -> None:
    print(render_boot_banner())


if __name__ == "__main__":
    main()
