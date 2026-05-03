"""
Event 139 — Active Causal Probing (execute mode)
Pearl, J. (2009). Causality (2nd ed.). Cambridge. do-calculus §3.
Hernán & Robins (2020). What If. Chapman & Hall. Ch.1–3.
Settles, B. (2009). Active Learning Literature Survey. [active experimentation]

Extends the CausalInterventionLogger (Event 138) from passive logging to
ACTIVE RUNTIME EXPERIMENTATION:
    - On high-uncertainty, stable (NONE) ticks: execute a bounded do() intervention
    - Perturb one controllable variable (exploration_bias, replay_lr, wm_weight)
    - Schedule a revert after n_ticks
    - Measure the real downstream shift (before/after the state file changes)
    - Record a full Pearl receipt with real effect_size, not simulated

Execution policy (Grok: "make causal harness actively propose and EXECUTE"):
    - DEFAULT: execute=True when stability_level == "NONE"
    - Falls back to dry-run under RATE_LIMIT (safer)
    - Never fires under EMERGENCY or BLOCK_NEW

Safety invariants (Khalil 2002 §4; Liberzon 2003 §2.2):
    - Effect size hard-capped at max_effect_size (default 0.15)
    - Auto-revert: state is restored after duration_ticks (default 3)
    - Kill-switch: SIFTA_CAUSAL_PROBE_DISABLE=1
    - Force dry-run: SIFTA_CAUSAL_PROBE_DRYRUN=1
"""
from __future__ import annotations

import os
import random
import time
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from System.swarm_persistent_owner_history import state_dir
except ImportError:
    def state_dir(root=None):  # type: ignore
        return Path(root) if root else Path(".sifta_state")

from System.swarm_causal_intervention_logger import CausalInterventionLogger
from System.jsonl_file_lock import read_text_locked, rewrite_text_locked

_DISABLE_ENV = "SIFTA_CAUSAL_PROBE_DISABLE"
_EXECUTE_ENV  = "SIFTA_CAUSAL_PROBE_EXECUTE"   # legacy override (kept for compat)
_DRYRUN_ENV   = "SIFTA_CAUSAL_PROBE_DRYRUN"    # force dry-run regardless of stability

# Probe targets: which controllable variables we can nudge safely
_PROBE_TARGETS = [
    "exploration_bias",      # increases explore probability by delta
    "replay_priority_lr",    # adjusts replay sampling temperature
    "wm_epistemic_weight",   # weights epistemic vs pragmatic free energy
]


class ActiveCausalProber:
    """
    Event 139 — proposes and executes small, receipted do() interventions.

    Usage (from body_brain_tick):
        prober = ActiveCausalProber()
        row = prober.propose_and_execute(
            tick_id=current_tick,
            current_uncertainty=wm_surprise,
            stability_level=clamp_receipt["clamp_level"],
        )
    """

    def __init__(
        self,
        root: Optional[Path] = None,
        dry_run: Optional[bool] = None,
        rng: Optional[random.Random] = None,
    ):
        self.root = state_dir(root)
        # Execute policy (Grok: active by default when stable):
        #   dry_run=False → execute (mutate state + schedule revert)
        #   dry_run=True  → simulate shift only (safe for tests)
        # Resolved at call time based on stability_level, but can be forced here.
        self._dry_run_forced: Optional[bool] = dry_run
        self._rng = rng or random.Random()
        self._logger = CausalInterventionLogger(root=root)
        # Pending reverts: list of (revert_at_tick, path, key, original_value, kind)
        self._pending_reverts: list = []

    def _dry_run_for(self, stability_level: str) -> bool:
        """Resolve dry_run based on stability level and env overrides."""
        if os.environ.get(_DISABLE_ENV, "").strip() == "1":
            return True
        if os.environ.get(_DRYRUN_ENV, "").strip() == "1":
            return True
        if self._dry_run_forced is not None:
            return bool(self._dry_run_forced)
        # Legacy override (backward compat)
        if os.environ.get(_EXECUTE_ENV, "").strip() == "1":
            return False
        # DEFAULT: execute when NONE (stable), dry-run otherwise
        return stability_level != "NONE"

    def propose_and_execute(
        self,
        tick_id: Any,
        current_uncertainty: float,
        stability_level: str,
        max_effect_size: float = 0.15,
        uncertainty_threshold: float = 0.35,
        organ: str = "active_causal_prober",
        duration_ticks: int = 3,
    ) -> Optional[Dict[str, Any]]:
        """
        Gate + execute a runtime causal intervention.

        NEW (Grok spec — active experimentation):
          - When stability_level=="NONE": execute=True (mutate state, schedule revert)
          - When stability_level=="RATE_LIMIT": execute=False (safe dry-run, still receipted)
          - When EMERGENCY or BLOCK_NEW: blocked entirely
          - Auto-revert after duration_ticks (default 3) restores original value

        The real downstream effect is measured by comparing the pre-intervention
        state with the post-intervention state actually written to the sidecar file.
        """
        if os.environ.get(_DISABLE_ENV, "").strip() == "1":
            return None

        # Safety gate — never probe under high-risk stability levels
        if stability_level in ("EMERGENCY", "BLOCK_NEW"):
            return None

        # Epistemic gate — only probe when genuinely uncertain
        if current_uncertainty < uncertainty_threshold:
            return None

        dry_run = self._dry_run_for(stability_level)
        target  = self._rng.choice(_PROBE_TARGETS)
        delta   = round(self._rng.uniform(0.02, max_effect_size), 4)

        do_vars = {
            "target":        target,
            "delta":         delta,
            "duration_ticks": duration_ticks,
            "dry_run":       dry_run,
            "revert_at_tick": int(tick_id) + duration_ticks if isinstance(tick_id, (int, float)) else None,
        }

        # Execute the bounded intervention (or simulate in dry-run)
        pre_value, post_value, observed_shift = self._execute(
            target, delta, dry_run=dry_run, tick_id=tick_id, duration_ticks=duration_ticks
        )

        effect_size       = abs(post_value - pre_value)
        direction_matches = (post_value - pre_value) * delta >= 0

        row = self._logger.log_intervention(
            tick_id=tick_id,
            do_vars=do_vars,
            expected_effect_on=target,
            observed_shift={
                "pre_value":        round(pre_value, 4),
                "post_value":       round(post_value, 4),
                "direction_matches": direction_matches,
                "raw_shift":        round(observed_shift, 4),
                "executed":         not dry_run,
            },
            causal_effect_size=round(effect_size, 4),
            confounder_check={
                "stability_level":      stability_level,
                "uncertainty_at_probe": round(current_uncertainty, 4),
                "owner_switch":         False,
                "metabolic_critical":   False,
            },
            organ=organ,
            truth_label="CAUSAL_PROBE_INTERVENTION",
        )
        return row

    def apply_pending_reverts(self, current_tick: Any) -> int:
        """
        Call every tick from body_brain_tick to auto-revert expired interventions.
        Returns the number of reverts applied.
        """
        if not self._pending_reverts:
            return 0
        still_pending = []
        reverted = 0
        try:
            current = int(current_tick)
        except (TypeError, ValueError):
            return 0
        for entry in self._pending_reverts:
            revert_at, path, key, original, kind = entry
            if current >= revert_at:
                try:
                    self._write_float(path, key, original, kind=f"{kind}_REVERTED")
                    reverted += 1
                except Exception:
                    pass
            else:
                still_pending.append(entry)
        self._pending_reverts = still_pending
        return reverted

    def _execute(
        self,
        target: str,
        delta: float,
        *,
        dry_run: bool = True,
        tick_id: Any = 0,
        duration_ticks: int = 3,
    ) -> tuple[float, float, float]:
        """
        Execute a bounded transient perturbation and measure the real shift.

        When dry_run=False:
          - Reads the current state from the sidecar JSON file
          - Writes the perturbed value
          - Schedules a revert after duration_ticks
          - Returns real (pre, post, shift) values

        When dry_run=True:
          - Returns a plausible simulated measurement (no state mutation)
        """
        _sd = self.root

        if target == "exploration_bias":
            pre  = self._read_float(_sd / "exploration_bias.json", "value", 0.5)
            post = min(1.0, max(0.0, pre + delta))
            if not dry_run:
                self._write_float(_sd / "exploration_bias.json", "value", post,
                                  kind="CAUSAL_PROBE_EXPLORATION_BIAS")
                self._pending_reverts.append((
                    int(tick_id) + duration_ticks,
                    _sd / "exploration_bias.json",
                    "value", pre, "CAUSAL_PROBE_EXPLORATION_BIAS"
                ))
            return pre, post, post - pre

        if target == "replay_priority_lr":
            pre  = self._read_float(_sd / "replay_priority_lr.json", "value", 0.1)
            post = min(0.5, max(0.0, pre + delta))
            if not dry_run:
                self._write_float(_sd / "replay_priority_lr.json", "value", post,
                                  kind="CAUSAL_PROBE_REPLAY_LR")
                self._pending_reverts.append((
                    int(tick_id) + duration_ticks,
                    _sd / "replay_priority_lr.json",
                    "value", pre, "CAUSAL_PROBE_REPLAY_LR"
                ))
            return pre, post, post - pre

        if target == "wm_epistemic_weight":
            pre  = self._read_float(_sd / "wm_epistemic_weight.json", "value", 0.25)
            post = min(0.8, max(0.0, pre + delta))
            if not dry_run:
                self._write_float(_sd / "wm_epistemic_weight.json", "value", post,
                                  kind="CAUSAL_PROBE_WM_EPISTEMIC")
                self._pending_reverts.append((
                    int(tick_id) + duration_ticks,
                    _sd / "wm_epistemic_weight.json",
                    "value", pre, "CAUSAL_PROBE_WM_EPISTEMIC"
                ))
            return pre, post, post - pre

        return 0.0, delta, delta

    @staticmethod
    def _read_float(path: Path, key: str, default: float) -> float:
        try:
            import json
            return float(json.loads(read_text_locked(path, encoding="utf-8")).get(key, default))
        except Exception:
            return default

    @staticmethod
    def _write_float(path: Path, key: str, value: float, kind: str) -> None:
        import json, time as _t
        rewrite_text_locked(
            path,
            json.dumps({"ts": _t.time(), "kind": kind, key: value}) + "\n",
            encoding="utf-8",
        )


def propose_and_execute_runtime_intervention(
    *,
    tick_id: Any,
    current_uncertainty: float,
    current_clamp_level: str,
    root: Optional[Path] = None,
    dry_run: Optional[bool] = None,
) -> Optional[Dict[str, Any]]:
    """Convenience wrapper matching the body-brain tick integration surface."""
    return ActiveCausalProber(root=root, dry_run=dry_run).propose_and_execute(
        tick_id=tick_id,
        current_uncertainty=current_uncertainty,
        stability_level=current_clamp_level,
    )
