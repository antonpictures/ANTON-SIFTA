import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Mapping

from System.stigmerobotics_virtual_physics_limb import simulate_limb_step
from System.stigmerobotics_textgen_limb import execute_textgen_request

@dataclass(frozen=True)
class EffectorRequest:
    trace_id: str
    target_body_id: str
    action_type: str  # e.g., "flash_screen", "play_tone", "vibrate"
    payload: dict[str, Any]
    source_ide: str
    homeworld_serial: str
    ts: float

@dataclass(frozen=True)
class EffectorReceipt:
    trace_id: str
    request_trace_id: str
    target_body_id: str
    status: str
    truth_note: str
    ts: float

def parse_effector_request(row: Mapping[str, Any]) -> EffectorRequest | None:
    if row.get("kind") != "effector_request":
        return None
    return EffectorRequest(
        trace_id=str(row.get("trace_id", "")),
        target_body_id=str(row.get("target_body_id", "")),
        action_type=str(row.get("action_type", "")),
        payload=dict(row.get("payload", {})),
        source_ide=str(row.get("source_ide", "")),
        homeworld_serial=str(row.get("homeworld_serial", "")),
        ts=float(row.get("ts", 0.0)),
    )

def execute_request_stub(request: EffectorRequest, now_ts: float) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """
    Executes a request without touching hardware (stub for tests).
    Returns a tuple of (effector_receipt_row, optional_sensor_echo_row).
    The sensor echo row is generated to satisfy the PhysicalSpaceReport continuity.
    """
    valid_targets = (
        "macbook_pro_screen",
        "iphone_tethered",
        "mac_speakers",
        "virtual_physics_limb",
        "textgen_limb",
        "abb_irb2400_virtual",
    )
    receipt_trace_id = str(uuid.uuid4())
    
    if request.target_body_id == "textgen_limb" and request.action_type == "generate_text":
        return execute_textgen_request(request, now_ts)
    
    if request.target_body_id not in valid_targets:
        receipt = {
            "ts": now_ts,
            "kind": "effector_receipt",
            "trace_id": receipt_trace_id,
            "request_trace_id": request.trace_id,
            "target_body_id": request.target_body_id,
            "status": "error",
            "truth_note": f"Target {request.target_body_id} unknown or missing explicit owner-consent.",
            "homeworld_serial": request.homeworld_serial,
            "source_ide": "effector_daemon"
        }
        return receipt, None

    # Success receipt
    receipt = {
        "ts": now_ts,
        "kind": "effector_receipt",
        "trace_id": receipt_trace_id,
        "request_trace_id": request.trace_id,
        "target_body_id": request.target_body_id,
        "status": "ok",
        "truth_note": f"Successfully simulated {request.action_type} on {request.target_body_id}",
        "homeworld_serial": request.homeworld_serial,
        "source_ide": "effector_daemon"
    }

    # Generate a sensor echo row mapped to the PhysicalSpaceReport aliases
    sensor_echo = None
    if request.action_type == "flash_screen":
        sensor_echo = {
            "ts": now_ts + 0.05,  # slight delay for sensor read
            "kind": "desk_telemetry_radar", 
            "body_id": request.target_body_id,
            "payload": {"lux_sample": 850.0},
            "distance_m": 0.0,
            "confidence": 0.95,
            "truth_label": "OBSERVED",
            "homeworld_serial": request.homeworld_serial
        }
    elif request.action_type == "vibrate":
        sensor_echo = {
            "ts": now_ts + 0.1,
            "kind": "desk_telemetry_radar",
            "body_id": request.target_body_id,
            "payload": {"imu_peak_g": 1.2},
            "distance_m": 0.4,
            "confidence": 0.90,
            "truth_label": "OBSERVED",
            "homeworld_serial": request.homeworld_serial
        }
    elif request.target_body_id == "abb_irb2400_virtual" and request.action_type == "set_joint_targets":
        joints = list(request.payload.get("joints_rad", []))
        sensor_echo = {
            "ts": now_ts + 0.05,
            "kind": "desk_telemetry_radar",
            "body_id": request.target_body_id,
            "payload": {
                "robot_model": request.payload.get("robot_model", "ABB_IRB2400"),
                "joints_rad": joints,
                "pose_mm": list(request.payload.get("pose_mm", [])),
                "orientation_rad": list(request.payload.get("orientation_rad", [])),
            },
            "pose_x": float(request.payload.get("pose_mm", [0.0, 0.0, 0.0])[0]) * 0.001,
            "pose_y": float(request.payload.get("pose_mm", [0.0, 0.0, 0.0])[1]) * 0.001,
            "pose_z": float(request.payload.get("pose_mm", [0.0, 0.0, 0.0])[2]) * 0.001,
            "confidence": 1.0,
            "truth_label": "OBSERVED",
            "homeworld_serial": request.homeworld_serial,
        }
    elif request.target_body_id == "virtual_physics_limb" and request.action_type == "apply_torque":
        current_state = request.payload.get("current_state", {"theta_rad": 0.0, "omega_rad_s": 0.0})
        torque = request.payload.get("torque_nm", 0.0)
        duration_ms = request.payload.get("duration_ms", 100.0)
        
        new_state, collision = simulate_limb_step(current_state, torque, duration_ms)
        
        sensor_echo = {
            "ts": now_ts + (duration_ms / 1000.0),
            "kind": "desk_telemetry_radar", # We classify virtual limb telemetry here
            "body_id": request.target_body_id,
            "payload": {
                "theta_rad": new_state["theta_rad"],
                "omega_rad_s": new_state["omega_rad_s"],
                "collision": collision
            },
            "distance_m": 0.5,
            "confidence": 1.0,
            "truth_label": "OBSERVED", # Truthfully represents the mathematical state of the limb
            "homeworld_serial": request.homeworld_serial
        }

    return receipt, sensor_echo
