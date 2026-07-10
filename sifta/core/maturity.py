#!/usr/bin/env python3
"""sifta.core.maturity — embodiment maturity matrix (DB6).

green / yellow / orange / red so no organ over-claims.
"""
from __future__ import annotations

from typing import Any

# status: green | yellow | orange | red
EMBODIMENT_MATURITY: list[dict[str, Any]] = [
    {
        "surface": "Mac body (power, thermal, display, volume, …)",
        "organ": "alice_hardware_body",
        "status": "green",
        "note": "Read/touch unprivileged macOS surfaces with receipts",
    },
    {
        "surface": "Camera / speech / shell effectors",
        "organ": "camera_eye / speech / swarm_shell_effector",
        "status": "yellow",
        "note": "Works with owner gates; STT/media bleed still hardening (r1602)",
    },
    {
        "surface": "Typed streams + blueprints + replay/sim",
        "organ": "sifta.core.*",
        "status": "yellow",
        "note": "r1603 spine landed; not a full robot SDK",
    },
    {
        "surface": "Virtual limbs / IRB2400 IK",
        "organ": "stigmerobotics_*",
        "status": "yellow",
        "note": "Code proof + virtual physics; metal motion HYPOTHESIS",
    },
    {
        "surface": "Real robot motion (Unitree / Reachy / Jetson motors)",
        "organ": "swarm_reachy_effector / jetson_motor / legs",
        "status": "red",
        "note": "Hypothesis until hardware receipt + sim/replay green",
    },
    {
        "surface": "MCP skill surface (ledger/shell)",
        "organ": "sifta_mcp_server",
        "status": "green",
        "note": "Receipt/scar discipline present",
    },
    {
        "surface": "MCP skills bound to live streams",
        "organ": "sifta.core.mcp_stream_skills",
        "status": "yellow",
        "note": "r1603 DB4 — get_color_image / relative_move / explore_room",
    },
]


def maturity_lines() -> list[str]:
    emoji = {"green": "🟩", "yellow": "🟨", "orange": "🟧", "red": "🟥"}
    lines = ["EMBODIMENT MATURITY MATRIX (r1603)"]
    for row in EMBODIMENT_MATURITY:
        mark = emoji.get(str(row["status"]), "⬜")
        lines.append(f"{mark} {row['surface']} — {row['organ']} — {row['note']}")
    return lines


def status_for(organ_substring: str) -> str:
    s = organ_substring.lower()
    for row in EMBODIMENT_MATURITY:
        if s in str(row.get("organ") or "").lower() or s in str(row.get("surface") or "").lower():
            return str(row["status"])
    return "unknown"
