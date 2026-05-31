"""
what_relates_creates.py
Two agents undergo significant mutual transformation only when they interact
through a shared field. Clear proof that the relationship itself creates the change.
"""

from dataclasses import dataclass, field
from typing import List

@dataclass
class Agent:
    id: str
    personality: float
    model_of_other: float = 0.5
    trust: float = 0.5
    history: List[float] = field(default_factory=list)

    def interact(self, other_personality_signal: float):
        # They are surprised by the actual signal from the other
        surprise = other_personality_signal - self.model_of_other
        self.model_of_other += 0.4 * surprise
        self.trust = min(1.0, self.trust + 0.07)
        self.history.append(self.model_of_other)

    def act_alone(self):
        self.trust *= 0.985


def run_coupled(rounds=18) -> tuple:
    a = Agent("A", personality=0.3)
    b = Agent("B", personality=0.8)
    for _ in range(rounds):
        a.interact(b.personality)
        b.interact(a.personality)
    return a, b

def run_isolated(rounds=18) -> tuple:
    a = Agent("A", personality=0.3)
    b = Agent("B", personality=0.8)
    for _ in range(rounds):
        a.act_alone()
        b.act_alone()
    return a, b
