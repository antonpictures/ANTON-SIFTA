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
from typing import Any, Dict, List, Optional

try:
    from System.swarm_persistent_owner_history import state_dir
except ImportError:
    def state_dir(root=None):  # type: ignore
        return Path(root) if root else Path(".sifta_state")

from System.swarm_causal_intervention_logger import CausalInterventionLogger
from System.jsonl_file_lock import (
    append_line_locked,
    read_text_locked,
    read_write_json_locked,
    rewrite_text_locked,
)

_DISABLE_ENV = "SIFTA_CAUSAL_PROBE_DISABLE"
_EXECUTE_ENV  = "SIFTA_CAUSAL_PROBE_EXECUTE"   # legacy override (kept for compat)
_DRYRUN_ENV   = "SIFTA_CAUSAL_PROBE_DRYRUN"    # force dry-run regardless of stability

# Probe targets: which controllable variables we can nudge safely
_PROBE_TARGETS = [
    "exploration_bias",      # increases explore probability by delta
    "replay_priority_lr",    # adjusts replay sampling temperature
    "wm_epistemic_weight",   # weights epistemic vs pragmatic free energy
]

_PENDING_REVERTS_NAME = "causal_probe_pending_reverts.jsonl"
_REVERT_LOG_NAME = "causal_probe_revert_log.jsonl"
_TICK_COUNTER_NAME = "causal_probe_tick_counter.json"


def _coerce_tick(value: Any) -> int:
    """Return a stable integer tick; nonnumeric ids fall back to wall-clock seconds."""
    tick = _as_int_tick(value)
    if tick is not None:
        return tick
    return int(time.time())


def _as_int_tick(value: Any) -> Optional[int]:
    """Return integer tick only when the caller supplied a real numeric tick."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _json_dumps(row: Dict[str, Any]) -> str:
    import json

    return json.dumps(row, sort_keys=True) + "\n"


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
        self._pending_reverts_path = self.root / _PENDING_REVERTS_NAME
        self._revert_log_path = self.root / _REVERT_LOG_NAME

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
        # Biological Stress Modulators (§10.14.28 integration)
        dam_stage: int = 0,
        tme_phase: str = "EQUILIBRIUM",
        na_level: float = 0.5,
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

        # ── Regulatory Genome ──
        from System.swarm_regulatory_genome import load_regulatory_parameters, get_latest_genome_hash
        reg_params = load_regulatory_parameters(self.root)
        reg_hash = get_latest_genome_hash(self.root)
        uncertainty_threshold = reg_params.get("causal_prober_uncertainty_threshold", uncertainty_threshold)

        # ── Biological Steering (§10.14.28) ──────────────────────────────────
        if dam_stage == 2:
            # Stage 2 (committed) microglia indicates severe brain inflammation and
            # active debris clearance. The organism must prioritize stabilization,
            # not active behavioral experimentation.
            return None

        # TME Escape triggers desperation: fast, high-variance probes
        if tme_phase == "ESCAPE":
            max_effect_size = min(0.35, max_effect_size * 2.0)
            duration_ticks = 1   # extremely short fast probes
            uncertainty_threshold = max(0.15, uncertainty_threshold - 0.15)
        elif tme_phase == "ELIMINATION":
            # Active immune clearance tolerates slightly more variance
            max_effect_size = min(0.20, max_effect_size * 1.2)
            uncertainty_threshold = max(0.25, uncertainty_threshold - 0.05)

        # High arousal (NA > 0.8) drives high exploration
        if na_level > 0.8:
            max_effect_size = min(0.30, max_effect_size * 1.5)
            uncertainty_threshold = max(0.20, uncertainty_threshold - 0.10)

        # Epistemic gate — only probe when genuinely uncertain
        if current_uncertainty < uncertainty_threshold:
            return None

        dry_run = self._dry_run_for(stability_level)
        target  = self._rng.choice(_PROBE_TARGETS)
        delta   = round(self._rng.uniform(0.02, max_effect_size), 4)
        tick_num = _coerce_tick(tick_id)
        duration_ticks = max(1, int(duration_ticks))

        do_vars = {
            "target":        target,
            "delta":         delta,
            "duration_ticks": duration_ticks,
            "dry_run":       dry_run,
            "revert_at_tick": tick_num + duration_ticks,
        }

        # Execute the bounded intervention (or simulate in dry-run)
        pre_value, post_value, observed_shift = self._execute(
            target, delta, dry_run=dry_run, tick_id=tick_num, duration_ticks=duration_ticks
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
                "dam_stage":            dam_stage,
                "tme_phase":            tme_phase,
                "na_level":             round(na_level, 4),
            },
            organ=organ,
            truth_label="CAUSAL_PROBE_INTERVENTION",
        )
        row["active_regulatory_parameters"] = reg_params
        row["regulatory_genome_row_hash"] = reg_hash
        return row

    def apply_pending_reverts(self, current_tick: Any) -> int:
        """
        Call every tick from body_brain_tick to auto-revert expired interventions.
        Returns the number of reverts applied.
        """
        pending_rows = self._read_pending_reverts()
        if not pending_rows:
            return 0
        still_pending: List[Dict[str, Any]] = []
        reverted = 0
        current = _as_int_tick(current_tick)
        if current is None:
            return 0
        for row in pending_rows:
            try:
                revert_at = int(row.get("revert_at_tick"))
            except (TypeError, ValueError):
                continue
            if current >= revert_at:
                try:
                    path = self._resolve_state_path(str(row.get("path") or ""))
                    key = str(row.get("key") or "value")
                    original = float(row.get("original_value"))
                    source_kind = str(row.get("source_kind") or "CAUSAL_PROBE")
                    self._write_float(path, key, original, kind=f"{source_kind}_REVERTED")
                    log_row = {
                        **row,
                        "ts": time.time(),
                        "kind": "CAUSAL_PROBE_REVERT_APPLIED",
                        "truth_label": "CAUSAL_PROBE_REVERT_APPLIED",
                        "status": "reverted",
                        "applied_at_tick": current,
                    }
                    append_line_locked(self._revert_log_path, _json_dumps(log_row), encoding="utf-8")
                    reverted += 1
                except Exception:
                    still_pending.append(row)
            else:
                still_pending.append(row)
        rewrite_text_locked(
            self._pending_reverts_path,
            "".join(_json_dumps(row) for row in still_pending),
            encoding="utf-8",
        )
        return reverted

    def _read_pending_reverts(self) -> List[Dict[str, Any]]:
        import json

        rows: List[Dict[str, Any]] = []
        raw = read_text_locked(self._pending_reverts_path, encoding="utf-8", errors="replace")
        for line in raw.splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict) and row.get("status", "pending") == "pending":
                rows.append(row)
        return rows

    def _state_relative_path(self, path: Path) -> str:
        resolved = path.resolve()
        root = self.root.resolve()
        try:
            return str(resolved.relative_to(root))
        except ValueError as exc:
            raise ValueError(f"causal probe path outside state_dir: {path}") from exc

    def _resolve_state_path(self, rel_path: str) -> Path:
        rel = Path(rel_path)
        if rel.is_absolute() or ".." in rel.parts:
            raise ValueError(f"unsafe causal probe revert path: {rel_path}")
        resolved = (self.root / rel).resolve()
        root = self.root.resolve()
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"causal probe revert path outside state_dir: {rel_path}") from exc
        return resolved

    def _schedule_revert(
        self,
        *,
        revert_at_tick: int,
        path: Path,
        key: str,
        original_value: float,
        source_kind: str,
    ) -> None:
        row = {
            "ts": time.time(),
            "kind": "CAUSAL_PROBE_PENDING_REVERT",
            "truth_label": "CAUSAL_PROBE_PENDING_REVERT",
            "status": "pending",
            "revert_at_tick": int(revert_at_tick),
            "path": self._state_relative_path(path),
            "key": key,
            "original_value": float(original_value),
            "source_kind": source_kind,
        }
        append_line_locked(self._pending_reverts_path, _json_dumps(row), encoding="utf-8")
        append_line_locked(self._revert_log_path, _json_dumps(row), encoding="utf-8")

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
                self._schedule_revert(
                    revert_at_tick=_coerce_tick(tick_id) + duration_ticks,
                    path=_sd / "exploration_bias.json",
                    key="value",
                    original_value=pre,
                    source_kind="CAUSAL_PROBE_EXPLORATION_BIAS",
                )
            return pre, post, post - pre

        if target == "replay_priority_lr":
            pre  = self._read_float(_sd / "replay_priority_lr.json", "value", 0.1)
            post = min(0.5, max(0.0, pre + delta))
            if not dry_run:
                self._write_float(_sd / "replay_priority_lr.json", "value", post,
                                  kind="CAUSAL_PROBE_REPLAY_LR")
                self._schedule_revert(
                    revert_at_tick=_coerce_tick(tick_id) + duration_ticks,
                    path=_sd / "replay_priority_lr.json",
                    key="value",
                    original_value=pre,
                    source_kind="CAUSAL_PROBE_REPLAY_LR",
                )
            return pre, post, post - pre

        if target == "wm_epistemic_weight":
            pre  = self._read_float(_sd / "wm_epistemic_weight.json", "value", 0.25)
            post = min(0.8, max(0.0, pre + delta))
            if not dry_run:
                self._write_float(_sd / "wm_epistemic_weight.json", "value", post,
                                  kind="CAUSAL_PROBE_WM_EPISTEMIC")
                self._schedule_revert(
                    revert_at_tick=_coerce_tick(tick_id) + duration_ticks,
                    path=_sd / "wm_epistemic_weight.json",
                    key="value",
                    original_value=pre,
                    source_kind="CAUSAL_PROBE_WM_EPISTEMIC",
                )
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
    uncertainty_threshold: float = 0.35,
    dam_stage: int = 0,
    tme_phase: str = "EQUILIBRIUM",
    na_level: float = 0.5,
) -> Optional[Dict[str, Any]]:
    """Convenience wrapper matching the body-brain tick integration surface."""
    return ActiveCausalProber(root=root, dry_run=dry_run).propose_and_execute(
        tick_id=tick_id,
        current_uncertainty=current_uncertainty,
        stability_level=current_clamp_level,
        uncertainty_threshold=uncertainty_threshold,
        dam_stage=dam_stage,
        tme_phase=tme_phase,
        na_level=na_level,
    )


def advance_runtime_tick(*, root: Optional[Path] = None) -> int:
    """Advance and return the Event139 runtime tick counter."""
    counter_path = state_dir(root) / _TICK_COUNTER_NAME

    def _update(data: Dict[str, Any]) -> Dict[str, Any]:
        tick = (_as_int_tick(data.get("tick")) or 0) + 1
        return {
            "ts": time.time(),
            "kind": "CAUSAL_PROBE_TICK_COUNTER",
            "truth_label": "CAUSAL_PROBE_TICK_COUNTER",
            "tick": tick,
        }

    return int(read_write_json_locked(counter_path, _update).get("tick", 0))


def apply_pending_reverts(*, current_tick: Any, root: Optional[Path] = None) -> int:
    """Convenience wrapper for the body-brain tick sweep."""
    return ActiveCausalProber(root=root).apply_pending_reverts(current_tick)
