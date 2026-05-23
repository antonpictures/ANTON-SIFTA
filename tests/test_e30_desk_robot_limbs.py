import time

from System.stigmerobotics_physical_space import (
    build_physical_space_report,
)

def test_desk_limb_lid_close_falsifier():
    """
    E30-desk falsifier slice. 
    The MacBook Pro + monitors + router + USB act as the desk robot limb.
    This test verifies that a hardware event (e.g., lid-close or uplink-loss) 
    is correctly wired into observability receipts via PhysicalSpaceReport.
    """
    now = time.time()
    
    # 1. Simulated receipt row for a MacBook lid close / uplink loss
    lid_close_row = {
        "ts": now - 0.5,
        "kind": "desk_telemetry_radar",  # Treated as desk limb telemetry
        "body_id": "macbook_pro_lid",
        "payload": {
            "lid_state": "closed",
            "uplink_state": "loss"
        },
        "distance_m": 0.0,  # Hardware is physically continuous at origin
        "confidence": 1.0,
        "truth_label": "OBSERVED",
        "homeworld_serial": "GTH4921YP3"
    }
    
    # 2. Build the physical space report
    report = build_physical_space_report(
        [lid_close_row], 
        now_ts=now,
        max_age_s=5.0
    )
    
    # 3. Assert the observability receipt is properly grounded
    assert report.grounded, "The desk limb event must ground the physical space."
    assert report.body_count == 1
    assert report.observations[0].body_id == "macbook_pro_lid"
    assert report.observations[0].sensor_kind == "desk_telemetry_radar"
    assert report.observations[0].homeworld_serial == "GTH4921YP3"
    
    proof = report.proof_of_property
    assert proof["truth_label"] == "OPERATIONAL"
    assert proof["observation_count"] == 1
