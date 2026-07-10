#!/usr/bin/env python3
"""sifta.core.mcp_stream_skills — MCP tools bound to live streams (DB4).

Skills:
  get_color_image → camera Out[Image] (or best-effort real eye)
  relative_move   → motor organ sim/real via cmd_vel In/Out
  explore_room    → navigation field deposit + receipt

Reuses MCP scar/receipt discipline when available.
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Optional

from sifta.core.stream import StreamBus, TYPE_IMAGE, TYPE_TWIST, wrap_camera_frame, wrap_cmd_vel

_REPO = Path(__file__).resolve().parents[2]
_STATE = _REPO / ".sifta_state"


def _scar(action: str, target: str = "") -> str:
    try:
        # Prefer live MCP scar if present
        from sifta_mcp_server import generate_scar  # type: ignore

        scar, _ts = generate_scar(action, target or None)
        return str(scar)
    except Exception:
        import hashlib

        h = hashlib.sha256(f"{action}_{target}_{time.time()}".encode()).hexdigest()[:12]
        return f"SCAR_{h}"


def _write_receipt(row: dict[str, Any], state_dir: Optional[Path] = None) -> Path:
    state = Path(state_dir) if state_dir else _STATE
    state.mkdir(parents=True, exist_ok=True)
    path = state / "mcp_stream_skill_receipts.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    return path


def get_color_image(
    bus: Optional[StreamBus] = None,
    *,
    state_dir: Optional[Path] = None,
) -> dict[str, Any]:
    """Return latest camera frame from stream bus, else probe real eye."""
    bus = bus or StreamBus()
    latest = bus.latest("camera", TYPE_IMAGE)
    payload: Any
    source = "stream"
    if latest is not None:
        payload = latest.payload
        source = latest.source or "stream"
    else:
        # best-effort real eye (may fail headless)
        try:
            from System.alice_hardware_body import AliceHardwareBody  # type: ignore

            # no guaranteed camera API — mark as absent
            payload = {"available": False, "reason": "no_frame_on_stream"}
            source = "probe"
        except Exception:
            payload = {"available": False, "reason": "no_camera_binding"}
            source = "probe"
        wrap_camera_frame(bus, payload, source=source)

    scar = _scar("get_color_image", source)
    row = {
        "truth_label": "MCP_STREAM_SKILL_V1",
        "skill": "get_color_image",
        "ts": time.time(),
        "receipt_id": uuid.uuid4().hex[:12],
        "scar": scar,
        "source": source,
        "image": payload,
    }
    _write_receipt(row, state_dir=state_dir)
    return row


def relative_move(
    forward: float = 0.0,
    angular: float = 0.0,
    *,
    bus: Optional[StreamBus] = None,
    mode: str = "simulation",
    state_dir: Optional[Path] = None,
) -> dict[str, Any]:
    """Publish cmd_vel. Default simulation — real requires hardware receipt path."""
    from sifta.core.replay import assert_sim_before_real

    bus = bus or StreamBus()
    twist = {"linear": float(forward), "angular": float(angular), "mode": mode}
    gate = assert_sim_before_real(
        claimed_mode=mode,
        replay_ok=mode == "replay",
        simulation_ok=mode in {"simulation", "sim", "replay"},
        real_hardware_receipt=False,
    )
    if mode == "real" and not gate["allowed"]:
        row = {
            "truth_label": "MCP_STREAM_SKILL_V1",
            "skill": "relative_move",
            "ts": time.time(),
            "receipt_id": uuid.uuid4().hex[:12],
            "scar": _scar("relative_move_blocked", mode),
            "ok": False,
            "gate": gate,
            "twist": twist,
            "claim": "HYPOTHESIS",
        }
        _write_receipt(row, state_dir=state_dir)
        return row

    wrap_cmd_vel(bus, twist, source=f"mcp_relative_move:{mode}")
    scar = _scar("relative_move", mode)
    row = {
        "truth_label": "MCP_STREAM_SKILL_V1",
        "skill": "relative_move",
        "ts": time.time(),
        "receipt_id": uuid.uuid4().hex[:12],
        "scar": scar,
        "ok": True,
        "gate": gate,
        "twist": twist,
        "claim": "SIMULATED_NOT_REAL_HARDWARE" if mode != "real" else "REAL_HARDWARE",
    }
    _write_receipt(row, state_dir=state_dir)
    return row


def explore_room(
    *,
    bus: Optional[StreamBus] = None,
    note: str = "",
    state_dir: Optional[Path] = None,
) -> dict[str, Any]:
    """Deposit explore intent into nav field stream + receipt."""
    bus = bus or StreamBus()
    intent = {
        "action": "explore_room",
        "note": note or "mcp explore",
        "ts": time.time(),
    }
    bus.publish("nav_intent", "NavIntent", intent, source="mcp_explore_room")
    # also nudge sim motion
    wrap_cmd_vel(bus, {"linear": 0.05, "angular": 0.1, "mode": "simulation"}, source="mcp_explore_room")
    scar = _scar("explore_room", note)
    row = {
        "truth_label": "MCP_STREAM_SKILL_V1",
        "skill": "explore_room",
        "ts": time.time(),
        "receipt_id": uuid.uuid4().hex[:12],
        "scar": scar,
        "ok": True,
        "intent": intent,
        "claim": "FIELD_DEPOSIT_SIM",
    }
    _write_receipt(row, state_dir=state_dir)
    return row


SKILL_HANDLERS = {
    "get_color_image": get_color_image,
    "relative_move": relative_move,
    "explore_room": explore_room,
}
