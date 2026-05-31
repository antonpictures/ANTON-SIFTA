import sys
sys.path.insert(0, "/Users/ioanganton/Music/ANTON_SIFTA")

from System.adaptation_lab.cognitive_light_cone import run_collective, run_isolated_agents

def test_collective_light_cone_larger():
    collective = run_collective(num_agents=10, steps=25, collective_goal=30)
    isolated = run_isolated_agents(num_agents=10, steps=25, individual_goal=8)
    
    assert collective > isolated + 5, f"Collective field {collective} should greatly exceed isolated max {isolated}"
