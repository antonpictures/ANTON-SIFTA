#!/usr/bin/env python3
"""
swarmrl_entropy_hooks.py — Where to wire λ → PPO entropy (trainer integration plan)
══════════════════════════════════════════════════════════════════════════════════

Perplexity / “fifth voice” summary (grounded):
  The bridge is **ordinary PPO**: entropy enters the actor loss as a **scalar**
  `entropy_coefficient` multiplying policy entropy. Scheduling that scalar from
  manifold pressure is **not** cross-tab magic — it is a **control loop** sitting
  above the optimizer.

References (DYOR):
  - Hugging Face — Deep RL / PPO intuition:
      https://huggingface.co/blog/deep-rl-ppo
  - Spinning Up — PPO:
      https://spinningup.openai.com/en/latest/algorithms/ppo.html
  - SwarmRL default c₂ = 0.01:
      `Archive/swarmrl_upstream/swarmrl/losses/proximal_policy_loss.py`
        (see `self.entropy_coefficient` in `_calculate_loss` / actor loss line)

Three shipped pieces (SIFTA repo today):
  1. **Pure schedule (Track A — λ)** — `System/lagrangian_entropy_controller.py`
  2. **Trainer hook (this module)** — `refresh_actor_critic_entropy(...)` /
     `refresh_from_manifold(...)` mutate `ProximalPolicyLoss.entropy_coefficient`.
  3. **Telemetry audit** — `ppo_entropy_bridge` + `stigmergic_entropy_trace_summary`.

**Track B (trace buffer):** `System/stigmergic_entropy_trace.py` — collective
rollout statistics → c₂ via `StigmergicEntropyController`; use
`refresh_from_stigmergic_buffer(...)` at the same trainer choke point **or**
compose with Track A via `refresh_entropy_dual_track(...)` /
`System/swarm_entropy_bridge.SiftaEntropyBridge`.

**Track A+B (composition):** `System/stigmergic_composition.py` — harmonic / min /
weighted mixer on **entropy coefficients** (not [0,1] clamp bug).

Where to call the hook in upstream SwarmRL (do **not** edit vendored code blindly;
subclass or fork `Archive/swarmrl_upstream`):

  A. **Best choke point** — `swarmrl.trainers.trainer.Trainer.update_rl`
     Insert **before** the `for agent in self.agents.values():` loop (see file
     around the loop that calls `agent.update_agent()`). One call per RL update
     refreshes c₂ for **all** species so `compute_loss` sees the new scalar.

  B. **Episode boundary** — `ContinuousTrainer.perform_rl_training` /
     `EpisodicTrainer.perform_rl_training` inner `for episode in range(n_episodes):`
     at the **top** of the body (before `integrate`) if you want c₂ fixed for the
     whole trajectory collection window.

Call flow (today’s SwarmRL):
  `perform_rl_training` → `engine.integrate(...)` → `update_rl()` →
  each `ActorCriticAgent.update_agent()` → `self.loss.compute_loss(...)` which
  uses `self.entropy_coefficient` (see `proximal_policy_loss.py`).

SIFTA λ source:
  `System.lagrangian_constraint_manifold.get_manifold().compute_dual_ascent()`
  → derive `lambda_norm` the same way `telemetry_snapshot.capture_snapshot` does
  (`total_lambda_penalty / 1.5`, clamp to 1).

This module intentionally avoids importing `swarmrl.*` so `PYTHONPATH=.` works
without adding `Archive/swarmrl_upstream` first — callers inside RL scripts add
that path and then call `refresh_actor_critic_entropy`.
"""
from __future__ import annotations

from typing import Any, Mapping, MutableMapping, Optional

from System.lagrangian_entropy_controller import entropy_coefficient_exponential
from System.stigmergic_composition import CompositionConfig, compose_entropy_coeff
from System.stigmergic_entropy_trace import StigmergicBuffer, StigmergicEntropyController
from System.swarm_entropy_bridge import lambda_norm_from_manifold


def refresh_actor_critic_entropy(
    agents: Mapping[str, Any],
    lambda_norm: float,
    *,
    c2_max: float = 0.01,
) -> dict[str, float]:
    """
    Duck-typed refresh for SwarmRL `Trainer.agents` dict values.

    Returns ``{"entropy_coefficient_c2": float}`` for logging / JSONL.
    """
    c2 = entropy_coefficient_exponential(lambda_norm, c2_max=c2_max)
    for agent in agents.values():
        loss = getattr(agent, "loss", None)
        if loss is not None and hasattr(loss, "entropy_coefficient"):
            setattr(loss, "entropy_coefficient", float(c2))
    return {"entropy_coefficient_c2": float(c2), "lambda_norm": float(lambda_norm)}


def refresh_from_manifold(agents: MutableMapping[str, Any]) -> dict[str, float]:
    """Convenience: read manifold, compute λ_norm like telemetry_snapshot, refresh."""
    lam_norm = lambda_norm_from_manifold()
    return refresh_actor_critic_entropy(agents, lam_norm)


def refresh_from_stigmergic_buffer(
    agents: MutableMapping[str, Any],
    buffer: StigmergicBuffer,
    controller: Optional[StigmergicEntropyController] = None,
) -> dict[str, float]:
    """Track B: set c₂ from collective trace statistics (SwarmGPT-style)."""
    ctrl = controller or StigmergicEntropyController()
    c2 = ctrl.compute_entropy_coef(buffer)
    for agent in agents.values():
        loss = getattr(agent, "loss", None)
        if loss is not None and hasattr(loss, "entropy_coefficient"):
            setattr(loss, "entropy_coefficient", float(c2))
    return {
        "entropy_coefficient_c2": float(c2),
        "mean_entropy": float(buffer.mean_entropy()),
        "mean_reward": float(buffer.mean_reward()),
        "track": "stigmergic_buffer",
    }


def refresh_entropy_dual_track(
    agents: MutableMapping[str, Any],
    buffer: StigmergicBuffer,
    *,
    composition: Optional[CompositionConfig] = None,
    trace_controller: Optional[StigmergicEntropyController] = None,
    c2_max: float = 0.01,
) -> dict[str, float]:
    """
    SwarmGPT composition primitive: one fused c₂ for all agents.

    Uses `compose_entropy_coeff` (default harmonic). Collapse heuristic:
    ``policy_collapse`` when fused coef is tiny and both tracks are tiny.
    """
    cfg = composition or CompositionConfig()
    lam = lambda_norm_from_manifold()
    c_l = entropy_coefficient_exponential(lam, c2_max=c2_max)
    ctrl = trace_controller or StigmergicEntropyController()
    c_t = ctrl.compute_entropy_coef(buffer)
    fused = compose_entropy_coeff(c_l, c_t, cfg)
    for agent in agents.values():
        loss = getattr(agent, "loss", None)
        if loss is not None and hasattr(loss, "entropy_coefficient"):
            setattr(loss, "entropy_coefficient", float(fused))
    collapse = bool(fused < 1e-4 and c_l < 1e-3 and c_t < 1e-3)
    return {
        "entropy_coefficient_c2": float(fused),
        "c_lambda": float(c_l),
        "c_trace": float(c_t),
        "lambda_norm": float(lam),
        "composition_mode": cfg.mode,
        "mean_entropy": float(buffer.mean_entropy()),
        "mean_reward": float(buffer.mean_reward()),
        "policy_collapse": collapse,
        "track": "dual_composed",
    }


__all__ = [
    "refresh_actor_critic_entropy",
    "refresh_from_manifold",
    "refresh_from_stigmergic_buffer",
    "refresh_entropy_dual_track",
]
