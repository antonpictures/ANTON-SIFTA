#!/usr/bin/env python3
"""
Bandit‑based hyperparameter tuner for heartbeat intervals.
Each interval is treated as an arm; reward = nutrients emitted per second.
"""

import json
import math
import time
from collections import defaultdict
from pathlib import Path

# Persistent storage for arm statistics
_STATS = Path(".sifta_state/hyperopt_stats.json")


def _load_stats() -> dict:
    if _STATS.exists():
        return json.loads(_STATS.read_text())
    return defaultdict(lambda: {"plays": 0, "reward": 0.0})


def _save_stats(stats: dict) -> None:
    _STATS.write_text(json.dumps(stats, indent=2))


def select_interval(arm_name: str, default: float) -> float:
    """UCB1 selection for a given arm."""
    stats = _load_stats()
    arm = stats[arm_name]
    total_plays = sum(v["plays"] for v in stats.values()) + 1
    if arm["plays"] == 0:
        return default  # explore initially
    avg_reward = arm["reward"] / arm["plays"]
    bonus = math.sqrt(2 * math.log(total_plays) / arm["plays"])
    return default * (1.0 + avg_reward + bonus)  # scale default


def update_reward(arm_name: str, reward: float) -> None:
    stats = _load_stats()
    arm = stats[arm_name]
    arm["plays"] += 1
    arm["reward"] += reward
    _save_stats(stats)


if __name__ == "__main__":
    # Demo: pretend we got 5 nutrients in 10 s for MICROBIOME
    update_reward("MICROBIOME", 0.5)  # 5/10
    print(select_interval("MICROBIOME", 45.0))
