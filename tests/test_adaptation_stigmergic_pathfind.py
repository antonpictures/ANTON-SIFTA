import sys
sys.path.insert(0, "/Users/ioanganton/Music/ANTON_SIFTA")

from System.adaptation_lab.stigmergic_pathfind import StigmergicGrid, random_baseline

def test_stigmergic_reaches_goal():
    g = StigmergicGrid(6, 6)
    g.run_ants(40, 25)
    assert g.get_best_path_length() < 35

def test_pheromone_exists():
    g = StigmergicGrid(5,5)
    g.deposit((2,2), 3.0)
    assert g.get_ph((2,2)) > 2.0
