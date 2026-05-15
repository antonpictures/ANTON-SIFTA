import pytest
from System.stigmerobotics_wet_dry_interface import wet_dry_bridge
from System.stigmerobotics_e48_physical_protocol import generate_protocol_for_spec, generate_all_protocols, LabProtocol

def test_generate_all_protocols():
    protocols = generate_all_protocols()
    bridge = wet_dry_bridge()
    assert len(protocols) == len(bridge.specs)
    assert len(protocols) > 0

def test_protocol_enforces_safety_gate():
    protocols = generate_all_protocols()
    for p in protocols:
        assert p.safety_gate_enforced
        assert p.is_valid
        assert "E48" in p.proof_of_property

def test_e33_specific_protocol():
    bridge = wet_dry_bridge()
    e33 = bridge.get_spec("E33")
    assert e33 is not None
    protocol = generate_protocol_for_spec(e33)
    assert protocol.hardware_target == "Opentrons_OT2"
    assert "opentrons" in protocol.script_content
    assert any("DISPENSE" in step for step in protocol.protocol_steps)

def test_protocol_truth_label():
    protocols = generate_all_protocols()
    for p in protocols:
        assert p.truth_label == "HYPOTHESIS"
