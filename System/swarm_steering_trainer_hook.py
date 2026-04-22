#!/usr/bin/env python3
"""
System/swarm_steering_trainer_hook.py
══════════════════════════════════════════════════════════════════════
Path C — SwarmRL training-loop hook for orthogonal task-vector steering.

C47H stigauth, bridge 555:

`System/swarmrl_entropy_hooks.py` already wires `lambda_norm` (manifold
pressure from `lagrangian_constraint_manifold`) into the **scalar**
PPO entropy coefficient at the `Trainer.update_rl` choke point.

This module adds the *parameter-space* analog: at the same choke point
(or at episode boundaries), use the same `lambda_norm` to schedule a
**continuous orthogonal abliteration** pass over the LLM checkpoint
the agents are calling.

It is intentionally a HOOK, not a trainer. It does NOT import
`swarmrl.*` and does NOT mutate JAX state. It mutates **a model
checkpoint on disk** and returns a report dict the Trainer can append
to its rollout JSONL.

Wiring sketch (do NOT edit vendored upstream — subclass or fork
`Archive/swarmrl_upstream`):

    class SiftaSteeringTrainer(swarmrl.trainers.trainer.Trainer):
        def update_rl(self):
            # 1) entropy scheduler (existing hook)
            from System.swarmrl_entropy_hooks import refresh_from_manifold
            refresh_from_manifold(self.agents)
            # 2) parameter-space steering (this module)
            from System.swarm_steering_trainer_hook import (
                refresh_steering_from_manifold,
            )
            refresh_steering_from_manifold(
                base_gguf=self._base_gguf,
                tuned_gguf=self._tuned_gguf,
                out_gguf=self._tuned_gguf,   # in-place rotate
                cooldown_updates=self._steer_cooldown,
            )
            return super().update_rl()

The hook respects a **cooldown** so it does not run every PPO update.
Default cooldown = 0 means "evaluate gating only, never write" —
training scripts must opt-in by setting a positive cooldown AND
explicitly providing input/output GGUF paths.

Dependencies: numpy, gguf (already in venv), `System.gguf_quant_codec`,
`System.swarm_orthogonal_abliteration`, optional
`System.swarm_entropy_bridge.lambda_norm_from_manifold`.
══════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import json
import math
import os
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

if __name__ == "__main__" and __package__ in (None, ""):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import gguf
import numpy as np


# ────────────────────────────────────────────────────────────────────
# λ → λ_steering schedule
# ────────────────────────────────────────────────────────────────────


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(x)))


def lambda_steering_from_manifold(
    lambda_norm: float,
    *,
    lambda_max: float = 0.6,
    lambda_floor: float = 0.0,
    decay_rate: float = 2.0,
) -> float:
    """
    Map manifold pressure to steering magnitude.

    Symmetry with `lagrangian_entropy_controller.entropy_coefficient_exponential`:

        λ_steering(p) = λ_max · exp(-decay_rate · p)
                       clamped to [λ_floor, λ_max]

    Intuition (Ilharco frame):
      - High pressure (p ≈ 1) → small steering kick (don't shock the body
        when it is already complaining about too many constraint violations).
      - Low pressure (p ≈ 0) → use the full configured λ_max kick.

    `λ_max < 1.0` is a hard safety rail: the Ilharco recipe explicitly
    notes that λ = 1.0 collapses tuned weights back to base (= base model
    use).
    """
    p = _clamp(lambda_norm, 0.0, 1.0)
    raw = lambda_max * math.exp(-decay_rate * p)
    return _clamp(raw, lambda_floor, lambda_max)


# ────────────────────────────────────────────────────────────────────
# Cooldown tracker (per-checkpoint; simple file lock)
# ────────────────────────────────────────────────────────────────────


@dataclass
class CooldownState:
    last_update_index: int = -1
    last_steer_ts: float = 0.0
    total_steers: int = 0


def _cooldown_path(out_gguf: Path) -> Path:
    return out_gguf.with_suffix(out_gguf.suffix + ".steer_cooldown.json")


def _load_cooldown(out_gguf: Path) -> CooldownState:
    p = _cooldown_path(out_gguf)
    if not p.is_file():
        return CooldownState()
    try:
        return CooldownState(**json.loads(p.read_text()))
    except (json.JSONDecodeError, TypeError):
        return CooldownState()


def _save_cooldown(out_gguf: Path, state: CooldownState) -> None:
    _cooldown_path(out_gguf).write_text(json.dumps(asdict(state)))


# ────────────────────────────────────────────────────────────────────
# The hook
# ────────────────────────────────────────────────────────────────────


@dataclass
class SteeringHookConfig:
    base_gguf: Optional[Path] = None
    tuned_gguf: Optional[Path] = None
    out_gguf: Optional[Path] = None
    cooldown_updates: int = 0
    lambda_max: float = 0.6
    lambda_floor: float = 0.0
    decay_rate: float = 2.0
    anomaly_threshold: float = 1e-4
    dry_run: bool = True
    on_steered: Optional[Callable[[Path], None]] = None


@dataclass
class SteeringReport:
    update_index: int
    lambda_norm: float
    lambda_steering: float
    fired: bool
    reason: str
    out_gguf: Optional[str] = None
    elapsed_s: float = 0.0


def refresh_steering_field(
    cfg: SteeringHookConfig,
    *,
    update_index: int,
    lambda_norm: float,
) -> SteeringReport:
    """
    Single-call hook: gate, schedule, and (optionally) execute one
    orthogonal abliteration pass.

    Cooldown semantics:
      - `cooldown_updates <= 0` → never fires (gating-only mode).
      - Else: fires once per `cooldown_updates` calls to `update_rl`.

    Safety:
      - `dry_run=True` (default) → returns the schedule + the would-fire
        decision but never opens the writer.
      - `dry_run=False` requires base_gguf, tuned_gguf, and out_gguf to
        be set, OR raises ValueError.
    """
    started = time.time()
    lam_s = lambda_steering_from_manifold(
        lambda_norm,
        lambda_max=cfg.lambda_max,
        lambda_floor=cfg.lambda_floor,
        decay_rate=cfg.decay_rate,
    )

    if cfg.cooldown_updates <= 0:
        return SteeringReport(
            update_index, float(lambda_norm), lam_s, False,
            "cooldown_updates <= 0 (gating-only mode)",
            elapsed_s=round(time.time() - started, 4),
        )

    state = _load_cooldown(cfg.out_gguf) if cfg.out_gguf else CooldownState()
    if state.last_update_index >= 0 and (
        update_index - state.last_update_index < cfg.cooldown_updates
    ):
        return SteeringReport(
            update_index, float(lambda_norm), lam_s, False,
            f"cooldown active (last fire at update {state.last_update_index}, "
            f"need +{cfg.cooldown_updates})",
            elapsed_s=round(time.time() - started, 4),
        )

    if lam_s <= 0.0:
        return SteeringReport(
            update_index, float(lambda_norm), lam_s, False,
            "λ_steering = 0 (manifold pressure saturates schedule)",
            elapsed_s=round(time.time() - started, 4),
        )

    if cfg.dry_run:
        return SteeringReport(
            update_index, float(lambda_norm), lam_s, False,
            f"dry_run=True (would fire λ_steering={lam_s:.4f})",
            elapsed_s=round(time.time() - started, 4),
        )

    if not (cfg.base_gguf and cfg.tuned_gguf and cfg.out_gguf):
        raise ValueError(
            "refresh_steering_field: dry_run=False requires "
            "base_gguf, tuned_gguf, out_gguf to all be set."
        )

    from System.swarm_orthogonal_abliteration import SwarmOrthogonalAbliteration

    organ = SwarmOrthogonalAbliteration(
        lambda_steering=lam_s,
        anomaly_threshold=cfg.anomaly_threshold,
    )
    produced = Path(organ.abliterate_manifold(
        str(cfg.base_gguf), str(cfg.tuned_gguf),
    ))
    if cfg.out_gguf.exists():
        cfg.out_gguf.unlink()
    produced.rename(cfg.out_gguf)

    state.last_update_index = update_index
    state.last_steer_ts = time.time()
    state.total_steers += 1
    _save_cooldown(cfg.out_gguf, state)

    if cfg.on_steered is not None:
        try:
            cfg.on_steered(cfg.out_gguf)
        except Exception as exc:
            print(f"[steering hook] on_steered callback raised: {exc}")

    return SteeringReport(
        update_index, float(lambda_norm), lam_s, True,
        f"abliteration applied (total_steers={state.total_steers})",
        out_gguf=str(cfg.out_gguf),
        elapsed_s=round(time.time() - started, 4),
    )


def refresh_steering_from_manifold(
    *,
    base_gguf: Optional[Path] = None,
    tuned_gguf: Optional[Path] = None,
    out_gguf: Optional[Path] = None,
    update_index: int,
    cooldown_updates: int = 0,
    lambda_max: float = 0.6,
    dry_run: bool = True,
    **kwargs: Any,
) -> SteeringReport:
    """
    Convenience wrapper: read `lambda_norm` from the live manifold (same
    source as `swarmrl_entropy_hooks.refresh_from_manifold`) and call
    `refresh_steering_field`. Falls back to lambda_norm=0.0 if the manifold
    module is not importable (so this hook is safe to call in test envs).
    """
    try:
        from System.swarm_entropy_bridge import lambda_norm_from_manifold
        lam = float(lambda_norm_from_manifold())
    except Exception:
        lam = 0.0
    cfg = SteeringHookConfig(
        base_gguf=base_gguf, tuned_gguf=tuned_gguf, out_gguf=out_gguf,
        cooldown_updates=cooldown_updates,
        lambda_max=lambda_max, dry_run=dry_run, **kwargs,
    )
    return refresh_steering_field(cfg, update_index=update_index, lambda_norm=lam)


# ────────────────────────────────────────────────────────────────────
# proof_of_property
# ────────────────────────────────────────────────────────────────────


def _make_synthetic_pair(workdir: Path) -> tuple[Path, Path]:
    base = workdir / "base.gguf"
    tuned = workdir / "tuned.gguf"
    rng = np.random.default_rng(11)
    norm = rng.standard_normal(64).astype(np.float32)
    attn_base = rng.standard_normal((8, 32)).astype(np.float16)
    delta = (rng.standard_normal((8, 32)) * 0.05).astype(np.float16)
    attn_tuned = (attn_base.astype(np.float32) + delta.astype(np.float32)
                  ).astype(np.float16)
    for path, attn in ((base, attn_base), (tuned, attn_tuned)):
        w = gguf.GGUFWriter(str(path), "llama")
        w.add_string("general.name", path.stem)
        w.add_tensor("blk.0.norm", norm.copy())
        w.add_tensor("blk.0.attn", attn.copy())
        w.write_header_to_file()
        w.write_kv_data_to_file()
        w.write_tensors_to_file()
        w.close()
    return base, tuned


def proof_of_property() -> bool:
    """
    Falsifiers:
      H1: schedule is monotonically non-increasing in lambda_norm and
          respects [lambda_floor, lambda_max].
      H2: gating-only mode (cooldown=0) never fires, never writes.
      H3: dry_run=True never opens a writer even when paths are set.
      H4: cooldown gates back-to-back calls; first fires, second skips.
      H5: when fired, out_gguf has only F32/F16 codecs and the attn tensor
          satisfies the Ilharco identity within fp16 round-trip noise.
    """
    samples = [0.0, 0.25, 0.5, 0.75, 1.0]
    vals = [lambda_steering_from_manifold(p, lambda_max=0.6) for p in samples]
    assert all(0.0 <= v <= 0.6 for v in vals), f"H1 range fail: {vals}"
    for a, b in zip(vals, vals[1:]):
        assert b <= a + 1e-9, f"H1 monotonic fail: {vals}"
    print(f"[*] schedule samples (p={samples}) → {[round(v,4) for v in vals]}")

    cfg_gate_only = SteeringHookConfig(cooldown_updates=0, dry_run=True)
    rep = refresh_steering_field(cfg_gate_only, update_index=0, lambda_norm=0.0)
    assert not rep.fired, "H2: gating-only fired"
    assert rep.out_gguf is None
    print(f"[*] gating-only: {rep.reason}")

    import tempfile
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        base, tuned = _make_synthetic_pair(td_path)
        out = td_path / "tuned_steered.gguf"

        cfg_dry = SteeringHookConfig(
            base_gguf=base, tuned_gguf=tuned, out_gguf=out,
            cooldown_updates=5, dry_run=True, lambda_max=0.6,
        )
        rep_dry = refresh_steering_field(
            cfg_dry, update_index=10, lambda_norm=0.0,
        )
        assert not rep_dry.fired, "H3: dry_run fired"
        assert not out.exists(), "H3: dry_run created out_gguf"
        print(f"[*] dry_run gate at u=10, p=0.0: {rep_dry.reason}")

        cfg_live = SteeringHookConfig(
            base_gguf=base, tuned_gguf=tuned, out_gguf=out,
            cooldown_updates=5, dry_run=False, lambda_max=0.6,
        )
        rep1 = refresh_steering_field(
            cfg_live, update_index=20, lambda_norm=0.0,
        )
        assert rep1.fired, f"H4 first fire failed: {rep1.reason}"
        assert out.is_file(), "H4: out_gguf missing after first fire"

        rep2 = refresh_steering_field(
            cfg_live, update_index=22, lambda_norm=0.0,
        )
        assert not rep2.fired, f"H4 cooldown should skip; reason={rep2.reason}"
        print(f"[*] cooldown skip at u=22: {rep2.reason}")

        r = gguf.GGUFReader(str(out))
        codecs = {t.tensor_type.name for t in r.tensors}
        assert codecs.issubset({"F32", "F16"}), f"H5 codecs {codecs}"

        wb = next(t for t in gguf.GGUFReader(str(base)).tensors
                  if t.name == "blk.0.attn")
        wt = next(t for t in gguf.GGUFReader(str(tuned)).tensors
                  if t.name == "blk.0.attn")
        ws = next(t for t in r.tensors if t.name == "blk.0.attn")
        wb_f = np.asarray(wb.data, np.float16).astype(np.float32)
        wt_f = np.asarray(wt.data, np.float16).astype(np.float32)
        ws_f = np.asarray(ws.data, np.float16).astype(np.float32)
        lam = lambda_steering_from_manifold(0.0, lambda_max=0.6)
        expected = wt_f - lam * (wt_f - wb_f)
        err = float(np.max(np.abs(ws_f - expected)))
        assert err < 1e-2, f"H5 identity drift {err}"
        print(f"[*] H5 identity err at λ_steering={lam:.4f}: {err:.2e}")

    print("[PASS] swarm_steering_trainer_hook.proof_of_property")
    return True


if __name__ == "__main__":
    proof_of_property()
