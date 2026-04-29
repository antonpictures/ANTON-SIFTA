#!/usr/bin/env python3
"""
System/swarm_cerebellum_timing.py — Cerebellar coordination / timing

Hypothalamus proposes *that* she should move; basal ganglia pick *which* action;
this organ smooths *how* it unfolds: expected latency, prediction error,
correction, and polite spacing so tool and social channels do not jitter.

Complements ``swarm_cerebellar_mcts.py`` (forward lookahead) and
``swarm_inferior_olive.py`` (slow value / climbing-fiber learning).

See: Documents/IDE_BOOT_COVENANT.md (append-only receipts, proof-bearing state).
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

_REPO = Path(__file__).resolve().parent.parent


@dataclass
class TimingUpdateResult:
    action: str
    expected_latency_before: float
    observed_latency: float
    timing_error: float
    next_expected_latency: float
    expected_success_before: float
    observed_success: float
    success_prediction_error: float
    next_expected_success: float
    ok: bool
    failure_streak: int

    def as_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "expected_latency_before": self.expected_latency_before,
            "observed_latency": self.observed_latency,
            "timing_error": self.timing_error,
            "next_expected_latency": self.next_expected_latency,
            "expected_success_before": self.expected_success_before,
            "observed_success": self.observed_success,
            "success_prediction_error": self.success_prediction_error,
            "next_expected_success": self.next_expected_success,
            "ok": self.ok,
            "failure_streak": self.failure_streak,
        }


class CerebellumTiming:
    """
    Fast forward model for per-action latency and success rate, with
    rate-aware ``should_delay`` for graceful pacing.
    """

    def __init__(
        self,
        *,
        correction_gain: float = 0.2,
        success_alpha: float = 0.25,
        default_expected_latency: float = 1.0,
        default_expected_success: float = 0.85,
        state_dir: Optional[Path] = None,
        persist_receipts: bool = True,
    ) -> None:
        self.expected_latency: Dict[str, float] = {}
        self.expected_success: Dict[str, float] = {}
        self.failure_streak: Dict[str, int] = {}
        self._last_end_ts: Dict[str, float] = {}
        self.correction_gain = float(correction_gain)
        self.success_alpha = float(success_alpha)
        self._default_lat = float(default_expected_latency)
        self._default_succ = float(default_expected_success)
        self._state = Path(state_dir) if state_dir is not None else _REPO / ".sifta_state"
        self._persist = bool(persist_receipts)
        self.ledger_path = self._state / "cerebellum_timing.jsonl"

    def predict(self, action: str) -> float:
        return float(self.expected_latency.get(action, self._default_lat))

    def predict_success(self, action: str) -> float:
        return float(self.expected_success.get(action, self._default_succ))

    def update(
        self,
        action: str,
        observed_latency: float,
        ok: bool,
        *,
        write_receipt: bool = True,
        now: Optional[float] = None,
    ) -> TimingUpdateResult:
        t = time.time() if now is None else float(now)
        exp_lat = self.predict(action)
        obs_lat = max(0.0, float(observed_latency))
        err = obs_lat - exp_lat
        new_lat = exp_lat + self.correction_gain * err
        new_lat = max(0.05, min(60.0, new_lat))
        self.expected_latency[action] = new_lat

        prev_s = self.predict_success(action)
        obs_s = 1.0 if ok else 0.0
        new_s = prev_s + self.success_alpha * (obs_s - prev_s)
        new_s = max(0.0, min(1.0, new_s))
        self.expected_success[action] = new_s
        succ_err = obs_s - prev_s

        if ok:
            self.failure_streak[action] = 0
        else:
            self.failure_streak[action] = int(self.failure_streak.get(action, 0)) + 1

        self._last_end_ts[action] = t

        result = TimingUpdateResult(
            action=action,
            expected_latency_before=exp_lat,
            observed_latency=obs_lat,
            timing_error=err,
            next_expected_latency=new_lat,
            expected_success_before=prev_s,
            observed_success=obs_s,
            success_prediction_error=succ_err,
            next_expected_success=new_s,
            ok=bool(ok),
            failure_streak=int(self.failure_streak[action]),
        )

        if write_receipt and self._persist:
            self._append_receipt(result, ts=t)

        return result

    def should_delay(
        self,
        action: str,
        urgency: float,
        *,
        now: Optional[float] = None,
    ) -> float:
        """
        Seconds to wait before starting the next instance of ``action``.

        High ``urgency`` (>0.8) bypasses delay (emergency / owner override path).
        Failures widen spacing; recent completions enforce a minimum gap.
        """
        t = time.time() if now is None else float(now)
        if float(urgency) > 0.8:
            return 0.0

        expected = self.predict(action)
        base = min(expected * 0.25, 2.0)
        streak = int(self.failure_streak.get(action, 0))
        caution = 1.0 + min(streak * 0.2, 2.0)
        delay = base * caution

        last = self._last_end_ts.get(action)
        if last is not None:
            min_gap = expected * (0.15 + 0.1 * float(streak))
            min_gap = max(0.0, min(min_gap, 4.0))
            elapsed = t - last
            burst = max(0.0, min_gap - elapsed)
            delay = delay + burst

        return float(min(delay, 5.0))

    def _append_receipt(self, result: TimingUpdateResult, *, ts: float) -> None:
        self._state.mkdir(parents=True, exist_ok=True)
        row = {
            "kind": "cerebellum_timing_correction",
            "ts": ts,
            **result.as_dict(),
        }
        line = json.dumps(row, separators=(",", ":"), sort_keys=True) + "\n"
        try:
            from System.jsonl_file_lock import append_line_locked

            append_line_locked(self.ledger_path, line)
        except ImportError:
            with self.ledger_path.open("a", encoding="utf-8") as fh:
                fh.write(line)

    def load_from_snapshot(self, snap: Mapping[str, Any]) -> None:
        """Restore in-memory state (e.g. from tests or checkpoint)."""
        lat = snap.get("expected_latency")
        if isinstance(lat, dict):
            self.expected_latency = {str(k): float(v) for k, v in lat.items()}
        succ = snap.get("expected_success")
        if isinstance(succ, dict):
            self.expected_success = {str(k): float(v) for k, v in succ.items()}
        fs = snap.get("failure_streak")
        if isinstance(fs, dict):
            self.failure_streak = {str(k): int(v) for k, v in fs.items()}
        le = snap.get("last_end_ts")
        if isinstance(le, dict):
            self._last_end_ts = {str(k): float(v) for k, v in le.items()}

    def snapshot(self) -> Dict[str, Any]:
        return {
            "expected_latency": dict(self.expected_latency),
            "expected_success": dict(self.expected_success),
            "failure_streak": dict(self.failure_streak),
            "last_end_ts": dict(self._last_end_ts),
        }
