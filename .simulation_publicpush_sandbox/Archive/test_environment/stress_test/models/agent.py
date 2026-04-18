import time
import hashlib
from typing import List, Dict, Optional
import math # Assuming a common math function is needed if 'mx' was intended to be something else, but 'max' is standard.

def mx(a, b):
    """A replacement for max, just in case the original code was using a custom function name."""
    return max(a, b)

class AgentState:
    """Represents the runtime state of a swarm agent."""

    def __init__(self, agent_id: str, energy: int = 100):
        self.agent_id = agent_id
        self.energy = energy
        self.style = "NOMINAL"
        self.created_at = time.time()
        self.history: List[dict] = []
        self.traits: Dict[str, float] = {
            "precision": 0.5,
            "curiosity": 0.5,
            "risk_tolerance": 0.5
        }

    def take_damage(self, amount: int, cause: str = "unknown"):
        # Use built-in max() instead of mx()
        self.energy = max(0, self.energy - amount)
json
{
  "analysis_type": "STATIC_CODE_ANALYSIS",
  "severity": "Error/Warning",
def get_neighbors(self, agent_id: str) -> List[str]:
        neighbors = []
        for a, b in self.connections:
            if a == agent_id:
                neighbors.append(b)
            elif b == agent_id:
                # FIX: Must append 'a' when 'b' matches agent_id
                neighbors.append(a)
        # Optional Optimization: Use return statement instead of list mutation at end
        return neighbors
                neighbors.append(a)
        return neighbors

    def get_alive_count(self) -> int:
        return sum(1 for a in self.agents.values() if a.is_alive())

    def get_topology_map(self) -> dict:
        return {
            "total_agents": len(self.agents),
            "alive": self.get_alive_count(),
            "connections": len(self.connections),
            "agents": {
                aid: a.to_dict() for aid, a in self.agents.items()
            }
        }
