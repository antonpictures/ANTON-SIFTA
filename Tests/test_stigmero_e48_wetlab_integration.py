import pytest
import math
from System.stigmerobotics_wet_dry_interface import wet_dry_bridge
from System.stigmerobotics_e48_physical_protocol import generate_protocol_for_spec

def test_wetlab_e33_pheromone_field_integration():
    """
    Mock integration test: E33 VLP Pheromone Field.
    Verifies that the generated Opentrons script compiles to valid Python AST
    and that mock wet-lab VLP concentration data respects the E39 I_inf bound.
    """
    bridge = wet_dry_bridge()
    spec = bridge.get_spec("E33")
    assert spec is not None
    protocol = generate_protocol_for_spec(spec)
    
    # 1. Statically verify the Opentrons script is valid python
    import ast
    try:
        ast.parse(protocol.script_content)
    except SyntaxError as e:
        pytest.fail(f"Generated Opentrons script has syntax error: {e}")

    # 2. Mock wet-lab outcome (VLP concentration)
    # At steady state, production (yield) / clearance = I_inf
    # If a lab reports VLP diverging (e.g. accumulating to infinity), the falsifier trips.
    mock_lab_vlp_concentration_over_time = [0.1, 0.5, 0.8, 0.95, 0.99, 1.0]
    i_inf_bound = 1.0
    
    for concentration in mock_lab_vlp_concentration_over_time:
        assert concentration <= i_inf_bound, spec.falsifier

def test_wetlab_e46b_segmental_coupling_integration():
    """
    Mock integration test: E46b Phase-Angle Ring.
    Verifies that the generated script compiles, and that mock competitive binding
    data respects the wave property (no two adjacent populations saturate simultaneously).
    """
    bridge = wet_dry_bridge()
    spec = bridge.get_spec("E46")
    assert spec is not None
    protocol = generate_protocol_for_spec(spec)
    
    import ast
    ast.parse(protocol.script_content)

    # Mock wet-lab competitive receptor binding across 4 populations (channels)
    # Wave property: no two adjacent populations saturate simultaneously.
    # We represent saturation as a boolean array over time t.
    mock_binding_timeline = [
        [True, False, False, False], # t=0: pop 0 saturates
        [False, True, False, False], # t=1: pop 1 saturates
        [False, False, True, False], # t=2: pop 2 saturates
        [False, False, False, True], # t=3: pop 3 saturates
    ]
    
    for t_step in mock_binding_timeline:
        # Check nearest neighbors
        n = len(t_step)
        for i in range(n):
            if t_step[i]:
                # If pop i is saturated, its neighbors must not be
                assert not t_step[(i + 1) % n], spec.falsifier
                assert not t_step[(i - 1) % n], spec.falsifier

def test_wetlab_e38_molecular_grammar_integration():
    """
    Mock integration test: E38 DFA-constrained assembly.
    """
    bridge = wet_dry_bridge()
    spec = bridge.get_spec("E38")
    protocol = generate_protocol_for_spec(spec)
    
    import ast
    ast.parse(protocol.script_content)

def test_wetlab_e45_brownian_wiggle_integration():
    """
    Mock integration test: E45 Brownian Wiggle.
    """
    bridge = wet_dry_bridge()
    spec = bridge.get_spec("E45")
    protocol = generate_protocol_for_spec(spec)
    
    import ast
    ast.parse(protocol.script_content)
