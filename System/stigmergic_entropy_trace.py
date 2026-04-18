#!/usr/bin/env python3
"""
stigmergic_entropy_trace.py — Trace-buffer entropy adaptation (SwarmGPT spec, hardened)
══════════════════════════════════════════════════════════════════════════════════════

**Coordination (stigmergy):** Cursor ships this module + telemetry + IDE handoff;
Antigravity wires SwarmRL trainer calls + validates JAX step counts. Do not race
edits on `Archive/swarmrl_upstream/` — fork or thin subclass in `System/` first.

**Dual tracks (do not conflate):**

  | Track | Driver | Module |
  |-------|--------|--------|
  | **A** | Manifold λ_norm → c₂ | `lagrangian_entropy_controller.py` + `swarmrl_entropy_hooks.refresh_from_manifold` |
  | **B** | Collective rollout traces (mean entropy / reward) | **this file** + `swarmrl_entropy_hooks.refresh_from_stigmergic_buffer` |

  Composition policy (pick one per experiment, or multiply with clamps):
  - `c2 = clamp( λ_track * trace_track )` — document in trainer; no hidden defaults here.

**Persistence:** optional append to `.sifta_state/stigmergic_entropy_events.jsonl`
under **POSIX flock** (same family as `ide_stigmergic_bridge`). SwarmGPT’s raw
`open(path,"w")` JSON dump is **not** used for multi-writer safety.

**Testing:** `python System/stigmergic_entropy_trace.py`
"""
from __future__ import annotations

import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, List, Optional

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.jsonl_file_lock import append_line_locked, read_text_locked  # noqa: E402

_STATE = _REPO / ".sifta_state"
DEFAULT_EVENTS_PATH = _STATE / "stigmergic_entropy_events.jsonl"


@dataclass
class StigmergicEvent:
    step: int
    agent_id: int
    entropy: float
    reward: float
    action_std: float
    ts: float = 0.0

    def __post_init__(self) -> None:
        if self.ts == 0.0:
            object.__setattr__(self, "ts", time.time())


class StigmergicBuffer:
    """In-memory ring + optional flock-append JSONL for cross-process traces."""

    def __init__(self, maxlen: int = 1000, *, persist_path: Optional[Path] = None):
        self.maxlen = int(maxlen)
        self.buffer: List[StigmergicEvent] = []
        self.persist_path = persist_path

    def log(self, event: StigmergicEvent) -> None:
        self.buffer.append(event)
        if len(self.buffer) > self.maxlen:
            self.buffer.pop(0)
        if self.persist_path is not None:
            line = json.dumps(asdict(event), ensure_ascii=False) + "\n"
            append_line_locked(self.persist_path, line, encoding="utf-8")

    def mean_entropy(self) -> float:
        if not self.buffer:
            return 0.0
        return sum(e.entropy for e in self.buffer) / len(self.buffer)

    def mean_reward(self) -> float:
        if not self.buffer:
            return 0.0
        return sum(e.reward for e in self.buffer) / len(self.buffer)

    def hydrate_from_jsonl(self, path: Optional[Path] = None, *, max_lines: int = 2000) -> int:
        """Load recent events from disk into the ring (newest bias). Returns count."""
        p = path or self.persist_path or DEFAULT_EVENTS_PATH
        if not p.exists():
            return 0
        raw = read_text_locked(p, encoding="utf-8", errors="replace")
        lines = [ln.strip() for ln in raw.splitlines() if ln.strip()][-max_lines:]
        n = 0
        for ln in lines:
            try:
                d = json.loads(ln)
                ev = StigmergicEvent(
                    step=int(d["step"]),
                    agent_id=int(d["agent_id"]),
                    entropy=float(d["entropy"]),
                    reward=float(d["reward"]),
                    action_std=float(d["action_std"]),
                    ts=float(d.get("ts", 0.0)),
                )
                self.buffer.append(ev)
                if len(self.buffer) > self.maxlen:
                    self.buffer.pop(0)
                n += 1
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                continue
        return n


class StigmergicEntropyController:
    """
    Entropy coefficient from collective trace statistics (SwarmGPT core idea).

    mean_reward / mean_entropy are clamped into sensible pressure ranges so
    unnormalized env rewards do not explode the coefficient.
    """

    def __init__(
        self,
        base_entropy: float = 0.01,
        exploration_gain: float = 1.5,
        exploitation_bias: float = 0.5,
        *,
        c_min: float = 1e-5,
        c_max: float = 0.05,
    ):
        self.base_entropy = float(base_entropy)
        self.exploration_gain = float(exploration_gain)
        self.exploitation_bias = float(exploitation_bias)
        self.c_min = float(c_min)
        self.c_max = float(c_max)

    def compute_entropy_coef(self, buffer: StigmergicBuffer) -> float:
        mean_entropy = max(0.0, min(1.0, buffer.mean_entropy()))
        mr = buffer.mean_reward()
        mean_reward = max(0.0, min(1.0, mr))  # treat as normalized return proxy

        stability_pressure = 1.0 - mean_entropy
        performance_pressure = 1.0 - mean_reward

        entropy_coeff = self.base_entropy * (
            self.exploration_gain * performance_pressure
            + self.exploitation_bias * stability_pressure
        )
        return float(max(self.c_min, min(entropy_coeff, self.c_max)))


def summarize_trace_file(path: Path = DEFAULT_EVENTS_PATH, *, tail_lines: int = 500) -> dict[str, Any]:
    """Read-only stats for telemetry (no mutation)."""
    buf = StigmergicBuffer(maxlen=tail_lines, persist_path=None)
    n = buf.hydrate_from_jsonl(path, max_lines=tail_lines)
    ctrl = StigmergicEntropyController()
    c2 = ctrl.compute_entropy_coef(buf) if n else None
    return {
        "events_loaded": n,
        "mean_entropy": round(buf.mean_entropy(), 6) if n else None,
        "mean_reward": round(buf.mean_reward(), 6) if n else None,
        "trace_entropy_coefficient_c2": c2,
        "path": str(path.relative_to(_REPO)) if str(path).startswith(str(_REPO)) else str(path),
    }


if __name__ == "__main__":
    buf = StigmergicBuffer(maxlen=200, persist_path=None)
    ctrl = StigmergicEntropyController()
    for step in range(100):
        buf.log(
            StigmergicEvent(
                step=step,
                agent_id=0,
                entropy=0.2 + (step % 10) * 0.01,
                reward=min(1.0, 0.5 + (step % 7) * 0.02),
                action_std=0.1,
            )
        )
        if step % 20 == 0:
            print(f"step={step} c2={ctrl.compute_entropy_coef(buf):.6f} mean_r={buf.mean_reward():.3f}")
    print("ok")
