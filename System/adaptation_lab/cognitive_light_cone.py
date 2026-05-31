"""
cognitive_light_cone.py
Demonstrates that a collective (through field sharing) can pursue larger goals
than any individual part can achieve alone.
"""

from dataclasses import dataclass
from typing import List

@dataclass
class Agent:
    position: int
    goal: int
    memory: List[int]

    def step(self, field: List[float]):
        # Individual can only see locally
        if abs(self.position - self.goal) <= 1:
            return
        # Very limited individual view
        direction = 1 if self.goal > self.position else -1
        self.position += direction

    def contribute_to_field(self, field: List[float]):
        if 0 <= self.position < len(field):
            field[self.position] += 0.3

def run_collective(num_agents=8, steps=30, collective_goal=25) -> int:
    """Collective shares a field. Together they can push the 'frontier' much farther."""
    field = [0.0] * (collective_goal + 5)
    agents = [Agent(i * 2, collective_goal, []) for i in range(num_agents)]

    for _ in range(steps):
        for a in agents:
            a.step(field)
            a.contribute_to_field(field)

        # Field allows agents to "see" what others have achieved
        for a in agents:
            if field[a.position] > 0.5:
                # The collective signal lets agents jump ahead
                a.position = min(collective_goal, a.position + 2)

    frontier = max(a.position for a in agents)
    return frontier


def run_isolated_agents(num_agents=8, steps=30, individual_goal=8) -> int:
    """Same number of agents, but no shared field. Each limited to its own small cone."""
    agents = [Agent(i * 2, individual_goal, []) for i in range(num_agents)]
    for _ in range(steps):
        for a in agents:
            if abs(a.position - a.goal) > 0:
                a.position += 1 if a.goal > a.position else -1
    return max(a.position for a in agents)
