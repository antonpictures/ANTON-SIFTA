import sys
sys.path.insert(0, "/Users/ioanganton/Music/ANTON_SIFTA")

from System.adaptation_lab.what_relates_creates import run_coupled, run_isolated

def test_mutual_transformation_only_when_coupled():
    a1, b1 = run_coupled(18)
    a2, b2 = run_isolated(18)

    change_coupled = abs(a1.model_of_other - 0.5) + abs(b1.model_of_other - 0.5)
    change_isolated = abs(a2.model_of_other - 0.5) + abs(b2.model_of_other - 0.5)

    assert change_coupled > 0.25, "Coupled agents should transform"
    assert change_isolated < 0.08, "Isolated agents should barely change"
