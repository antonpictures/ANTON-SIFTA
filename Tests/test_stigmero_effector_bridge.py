import time
import uuid

from System.stigmerobotics_effector_bridge import (
    EffectorRequest,
    parse_effector_request,
    execute_request_stub
)
from System.stigmerobotics_physical_space import build_physical_space_report

def test_effector_bridge_roundtrip_flash_screen():
    now = time.time()
    
    # 1. The LLM / Policy layer proposes an effector request
    request_row = {
        "ts": now,
        "kind": "effector_request",
        "trace_id": str(uuid.uuid4()),
        "target_body_id": "iphone_tethered",
        "action_type": "flash_screen",
        "payload": {"color": "#FFFFFF", "duration_ms": 200},
        "source_ide": "Alice_Talk",
        "homeworld_serial": "GTH4921YP3"
    }
    
    request = parse_effector_request(request_row)
    assert request is not None
    assert request.action_type == "flash_screen"
    
    # 2. The executor stub reads the request and emits a receipt and sensor echo
    receipt_row, sensor_echo_row = execute_request_stub(request, now_ts=now + 0.1)
    
    assert receipt_row["status"] == "ok"
    assert receipt_row["kind"] == "effector_receipt"
    assert receipt_row["request_trace_id"] == request.trace_id
    
    assert sensor_echo_row is not None
    assert sensor_echo_row["kind"] == "desk_telemetry_radar"
    assert sensor_echo_row["payload"]["lux_sample"] > 0
    
    # 3. Continuity assertion: the sensor echo grounds the physical space
    report = build_physical_space_report([sensor_echo_row], now_ts=now + 0.2, max_age_s=5.0)
    
    assert report.grounded, "The effector's sensor echo must ground the physical space report."
    assert report.body_count == 1
    assert report.observations[0].body_id == "iphone_tethered"

def test_effector_bridge_quarantine_unknown_target():
    now = time.time()
    
    request_row = {
        "ts": now,
        "kind": "effector_request",
        "trace_id": str(uuid.uuid4()),
        "target_body_id": "unauthorized_drone",
        "action_type": "spin_rotors",
        "payload": {"rpm": 5000},
        "source_ide": "Alice_Talk",
        "homeworld_serial": "GTH4921YP3"
    }
    
    request = parse_effector_request(request_row)
    receipt_row, sensor_echo_row = execute_request_stub(request, now_ts=now + 0.1)
    
    assert receipt_row["status"] == "error"
    assert "unknown or missing explicit owner-consent" in receipt_row["truth_note"]
    assert sensor_echo_row is None  # No sensor echo for rejected hardware

def test_effector_bridge_virtual_physics_limb():
    now = time.time()
    
    # Send a request to apply torque to the virtual physics limb
    request_row = {
        "ts": now,
        "kind": "effector_request",
        "trace_id": str(uuid.uuid4()),
        "target_body_id": "virtual_physics_limb",
        "action_type": "apply_torque",
        "payload": {
            "current_state": {"theta_rad": 0.0, "omega_rad_s": 0.0},
            "torque_nm": 10.0, # Apply 10 Nm torque
            "duration_ms": 100.0 # Simulate for 100 ms
        },
        "source_ide": "Alice_Talk",
        "homeworld_serial": "GTH4921YP3"
    }
    
    request = parse_effector_request(request_row)
    assert request is not None
    
    receipt_row, sensor_echo_row = execute_request_stub(request, now_ts=now + 0.1)
    
    assert receipt_row["status"] == "ok"
    
    # We should get a sensor echo with updated physics
    assert sensor_echo_row is not None
    assert sensor_echo_row["kind"] == "desk_telemetry_radar"
    assert "theta_rad" in sensor_echo_row["payload"]
    assert "omega_rad_s" in sensor_echo_row["payload"]
    assert "collision" in sensor_echo_row["payload"]
    
    # Confirm it integrated into the physical space report
    report = build_physical_space_report([sensor_echo_row], now_ts=now + 0.2, max_age_s=5.0)
    assert report.grounded
    assert report.body_count == 1
    assert report.observations[0].body_id == "virtual_physics_limb"
