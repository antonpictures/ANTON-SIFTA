"""Reachy Mini effector stub for Alice.

This module records a narrow physical-effector surface for the Reachy robotics
thread. It does not talk to hardware yet. It only turns intended robot actions
into receipted swimmer rows so the body can integrate the organ next.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO = Path("/Users/ioanganton/Music/ANTON_SIFTA")
LEDGER = REPO / ".sifta_state" / "reachy_effector_organ.jsonl"
SUPPORTED_ACTIONS = ("move", "speak", "see", "gesture", "listen")


@dataclass(frozen=True)
class ReachyRequest:
    ts: float
    action_type: str
    payload: dict[str, Any]
    source_ide: str
    homeworld_serial: str
    target_body_id: str = "reachy_mini"


@dataclass(frozen=True)
class ReachyReceipt:
    ts: float
    trace_id: str
    request_trace_id: str
    target_body_id: str
    status: str
    truth_note: str
    action_type: str
    source_ide: str
    homeworld_serial: str
    extra: dict[str, Any] = field(default_factory=dict)


def build_reachy_plan(action_type: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = dict(payload or {})
    action = str(action_type or "").strip().lower()
    if action not in SUPPORTED_ACTIONS:
        return {
            "ok": False,
            "reason": "unsupported_reachy_action",
            "action_type": action_type,
            "supported_actions": SUPPORTED_ACTIONS,
        }
    return {
        "ok": True,
        "action_type": action,
        "payload": payload,
        "receipt_shape": "reachy_effector_organ.jsonl row with trace_id + request_trace_id + status",
        "truth_label": "REACHY_STIGMERGIC_EFFECTOR_V1",
    }


def _append_receipt(receipt: ReachyReceipt) -> str:
    trace_id = f"r200-reachy-{int(receipt.ts * 1000)}-{receipt.action_type}"
    row = {
        "ts": receipt.ts,
        "trace_id": trace_id,
        "request_trace_id": receipt.request_trace_id,
        "kind": "reachy_effector_receipt",
        "target_body_id": receipt.target_body_id,
        "action_type": receipt.action_type,
        "status": receipt.status,
        "truth_note": receipt.truth_note,
        "source_ide": receipt.source_ide,
        "homeworld_serial": receipt.homeworld_serial,
        "extra": receipt.extra,
        "truth_label": "REACHY_STIGMERGIC_EFFECTOR_V1",
    }
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")
    return trace_id


def execute_request_stub(request: ReachyRequest) -> dict[str, Any]:
    """Emit a local effector receipt without touching hardware."""
    ts = request.ts or time.time()
    request_trace_id = str(uuid.uuid4())
    plan = build_reachy_plan(request.action_type, request.payload)
    if not plan["ok"]:
        receipt = ReachyReceipt(
            ts=ts,
            trace_id="",
            request_trace_id=request_trace_id,
            target_body_id=request.target_body_id,
            status="error",
            truth_note=plan["reason"],
            action_type=request.action_type,
            source_ide=request.source_ide,
            homeworld_serial=request.homeworld_serial,
            extra={"supported_actions": plan["supported_actions"]},
        )
        trace_id = _append_receipt(receipt)
        return {"ok": False, "trace_id": trace_id, "request_trace_id": request_trace_id, "reason": plan["reason"], "ledger": str(LEDGER)}

    action = plan["action_type"]
    payload = dict(plan["payload"])
    sensor_echo: dict[str, Any] | None = None
    truth_note = f"Simulated Reachy {action} swimmer executed."
    extra: dict[str, Any] = {"payload": payload, "supported_actions": SUPPORTED_ACTIONS}

    if action == "see":
        sensor_echo = {
            "ts": ts + 0.05,
            "kind": "reachy_camera_observation",
            "body_id": request.target_body_id,
            "payload": {"frame_id": str(uuid.uuid4()), "objects": payload.get("objects", [])},
            "truth_label": "OBSERVED",
            "homeworld_serial": request.homeworld_serial,
        }
    elif action == "speak":
        sensor_echo = {
            "ts": ts + 0.05,
            "kind": "reachy_voice_observation",
            "body_id": request.target_body_id,
            "payload": {"utterance": payload.get("text", ""), "tts": payload.get("tts", "qwen3-tts")},
            "truth_label": "OBSERVED",
            "homeworld_serial": request.homeworld_serial,
        }
    elif action == "move":
        sensor_echo = {
            "ts": ts + 0.05,
            "kind": "reachy_motion_observation",
            "body_id": request.target_body_id,
            "payload": {
                "joint_targets": payload.get("joint_targets", {}),
                "duration_s": payload.get("duration_s", 1.0),
            },
            "truth_label": "OBSERVED",
            "homeworld_serial": request.homeworld_serial,
        }

    receipt = ReachyReceipt(
        ts=ts,
        trace_id="",
        request_trace_id=request_trace_id,
        target_body_id=request.target_body_id,
        status="ok",
        truth_note=truth_note,
        action_type=action,
        source_ide=request.source_ide,
        homeworld_serial=request.homeworld_serial,
        extra=extra,
    )
    trace_id = _append_receipt(receipt)
    return {
        "ok": True,
        "trace_id": trace_id,
        "request_trace_id": request_trace_id,
        "ledger": str(LEDGER),
        "sensor_echo": sensor_echo,
        "truth_label": "REACHY_STIGMERGIC_EFFECTOR_V1",
    }


def get_status() -> dict[str, Any]:
    return {
        "organ": "reachy_effector",
        "status": "stub_ready",
        "ledger": str(LEDGER),
        "supported_actions": SUPPORTED_ACTIONS,
        "hardware": "not_connected",
    }


if __name__ == "__main__":
    print(get_status())
