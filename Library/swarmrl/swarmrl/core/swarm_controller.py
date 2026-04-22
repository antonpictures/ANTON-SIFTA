#!/usr/bin/env python3
"""
swarm_controller.py — Central coordination scaffold for multi-agent rollouts.
══════════════════════════════════════════════════════════════════════════════
Engineering role (no replacement for :class:`swarmrl.trainers.trainer.Trainer`):
aggregate local observations into a **shared** summary, route per-agent decisions
through a single policy hook, and record swarm-level reward traces.

This mirrors **CTDE**-style patterns (centralized information at training / sync
time, decentralized execution at test time) discussed in multi-agent RL
literature — see SIFTA ``Documents/DYOR_SWARM_BIOLOGY_WEB_GATHER_2026-04-18.md`` §24.

Dependencies: **NumPy** only in the default path (matches upstream SwarmRL). If you
pass ``torch.Tensor`` observations, aggregation uses PyTorch when available.

Policy contract (one of):
  - ``policy.forward(obs, shared_state) -> action``
  - ``policy(obs, shared_state) -> action`` (callable)
══════════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Protocol, Sequence, Union

import numpy as np

try:
    import torch
except ImportError:  # pragma: no cover - optional
    torch = None  # type: ignore


class _PolicyFn(Protocol):
    def forward(self, obs: Any, shared_state: Any) -> Any: ...


class SwarmController:
    """
    Lightweight orchestration layer: shared latent summary + per-agent policy calls.

    Parameters
    ----------
    policy
        Object with ``forward(obs, shared)`` or a binary callable.
    memory
        Optional external dict; :meth:`update_memory` appends keyed entries.
    aggregate
        Optional callable ``(observations) -> shared_state`` overriding mean-pool.
    """

    def __init__(
        self,
        policy: Union[_PolicyFn, Callable[[Any, Any], Any]],
        memory: Optional[Dict[int, Any]] = None,
        aggregate: Optional[Callable[[Sequence[Any]], Any]] = None,
    ) -> None:
        self.policy = policy
        self.memory: Dict[int, Any] = memory if memory is not None else {}
        self.global_step = 0
        self._aggregate_fn = aggregate

    def aggregate_observations(self, observations: Sequence[Any]) -> Any:
        """Mean-pool observations along the agent axis (NumPy or torch)."""
        if self._aggregate_fn is not None:
            return self._aggregate_fn(observations)
        if not observations:
            raise ValueError("observations must be non-empty")
        first = observations[0]
        if torch is not None and isinstance(first, torch.Tensor):
            return torch.stack(list(observations), dim=0).mean(dim=0)
        arrs = [np.asarray(o, dtype=np.float64) for o in observations]
        return np.mean(np.stack(arrs, axis=0), axis=0)

    def select_actions(self, observations: Sequence[Any]) -> List[Any]:
        """Compute one action per agent using shared context."""
        shared_state = self.aggregate_observations(observations)
        actions: List[Any] = []
        for obs in observations:
            actions.append(self._policy_step(obs, shared_state))
        return actions

    def _policy_step(self, obs: Any, shared_state: Any) -> Any:
        pol = self.policy
        if hasattr(pol, "forward"):
            return pol.forward(obs, shared_state)  # type: ignore[no-any-return]
        if callable(pol):
            return pol(obs, shared_state)  # type: ignore[misc]
        raise TypeError(
            "policy must implement forward(obs, shared) or be callable(obs, shared)"
        )

    def update_memory(self, reward_signal: Any, swarm_state: Any) -> None:
        """Store a coarse swarm-level trace (debug / telemetry)."""
        self.memory[self.global_step] = {
            "reward": reward_signal,
            "state": swarm_state,
        }
        self.global_step += 1

    @staticmethod
    def compute_swarm_reward(rewards: Sequence[float]) -> float:
        """Mean cooperative return (extensible to weighted / min / CVaR)."""
        if not rewards:
            return 0.0
        return float(sum(rewards) / len(rewards))


if __name__ == "__main__":  # pragma: no cover
    class _Stub:
        def forward(self, obs, shared):  # noqa: ANN001
            return int(np.argmax(obs)) if hasattr(obs, "__len__") else 0

    c = SwarmController(_Stub())
    obs_batch = [np.array([0.0, 1.0, 0.0]), np.array([0.0, 0.5, 0.5])]
    print("shared:", c.aggregate_observations(obs_batch))
    print("actions:", c.select_actions(obs_batch))
    print("swarm_r:", c.compute_swarm_reward([0.2, 0.8]))
