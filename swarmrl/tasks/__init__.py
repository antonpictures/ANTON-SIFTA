"""swarmrl/tasks — SIFTA novel task library.

Tasks here implement the SwarmRL Task interface for use with
ESPResSo-backed simulations. They can also be run standalone
(without ESPResSo) using the graceful stubs in each module.

Novel tasks (Biocode Olympiad):
    StigmergicConsensus  — AS46/AG31 (Event 55)
        Local velocity alignment + cohesion + separation + activity.
        Physics: Vicsek 1995, Reynolds 1987, Lavergne 2019.
        No central controller, no oracle, no global target.
"""
from swarmrl.tasks.stigmergic_consensus import StigmergicConsensus
from swarmrl.tasks.stigmal_555 import Stigmal555

__all__ = ["StigmergicConsensus", "Stigmal555"]
