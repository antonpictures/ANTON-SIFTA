#!/usr/bin/env python3
"""
System/swarm_cerebellum_timing.py — Cerebellar forward model (Event 77)

Biocode Olympiad — **Event 77: Cerebellar Forward Model (Smith Predictor)**.

Biology: Purkinje / forward motor prediction; prevents ataxic over-correction when
sensory feedback is delayed (Basal Ganglia must not spam "retry" while the motor
loop is still in flight).

Physics / control: **Smith predictor** — hold an internal model of loop latency so
the organism can wait out the delay shadow instead of oscillating.

Wiring (Bishop / C55M / AG31):
  1. After Basal Ganglia selects an action, call ``should_delay(action, urgency)``.
  2. If return value > 0, yield the compute cycle (do not re-issue the command).
  3. After physical execution completes, call ``update(action, observed_latency, ok)``
     with wall-clock latency so the forward model tracks the host machine.

Complements ``swarm_cerebellar_mcts.py`` (lookahead) and
``swarm_inferior_olive.py`` (slow climbing-fiber value learning).

See: Documents/IDE_BOOT_COVENANT.md (append-only receipts).
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
    Biological Smith predictor + optional success EMA for audit.

    ``timing_error`` on receipts is the **learning error** (includes failure
    inflation per Bishop v1: failed outcomes push the model toward longer
    expected latency).
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
        self.last_fired_timestamp: Dict[str, float] = {}
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
        err_base = obs_lat - exp_lat
        err_learn = err_base + (exp_lat * 0.5 if not ok else 0.0)
        new_lat = exp_lat + self.correction_gain * err_learn
        new_lat = max(0.1, min(60.0, new_lat))
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

        result = TimingUpdateResult(
            action=action,
            expected_latency_before=exp_lat,
            observed_latency=obs_lat,
            timing_error=err_learn,
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
        Delay shadow for the Smith predictor.

        If ``now - last_fired < expected``, the command is treated as still **in
        flight**; return remaining wait (capped) unless ``urgency > 0.8``
        (sympathetic bypass). When the shadow has cleared, stamp
        ``last_fired_timestamp`` and return ``0.0`` (cleared to fire).

        Note: use wall-clock ``now`` in tests; at ``t=0`` the default missing
        last-fire reads as 0 and the first query sits in the shadow until
        ``now >= expected`` unless urgency bypasses.
        """
        t = time.time() if now is None else float(now)
        last_fired = float(self.last_fired_timestamp.get(action, 0.0))
        expected = self.predict(action)
        time_since_last = t - last_fired

        if time_since_last < expected:
            if float(urgency) > 0.8:
                return 0.0
            delay_needed = expected - time_since_last
            return float(min(delay_needed, expected * 1.5))

        self.last_fired_timestamp[action] = t
        return 0.0

    def _append_receipt(self, result: TimingUpdateResult, *, ts: float) -> None:
        self._state.mkdir(parents=True, exist_ok=True)
        row = {
            "kind": "cerebellum_timing_correction",
            "event": "BISHOP_EVENT_77",
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
        lf = snap.get("last_fired_timestamp")
        if isinstance(lf, dict):
            self.last_fired_timestamp = {str(k): float(v) for k, v in lf.items()}

    def snapshot(self) -> Dict[str, Any]:
        return {
            "expected_latency": dict(self.expected_latency),
            "expected_success": dict(self.expected_success),
            "failure_streak": dict(self.failure_streak),
            "last_fired_timestamp": dict(self.last_fired_timestamp),
        }


SwarmCerebellumTiming = CerebellumTiming


def proof_of_property() -> bool:
    """
    Bishop mandate verification — numerically checks Smith shadow + urgency.
    Uses wall-clock time for Phase 3 (small sleep) like the .dirt reference.
    """
    print("\n=== SIFTA CEREBELLAR FORWARD MODEL (Event 77) : JUDGE VERIFICATION ===")
    cerebellum = CerebellumTiming(
        correction_gain=0.5,
        default_expected_latency=1.0,
        persist_receipts=False,
    )
    action = "execute_terminal_command"

    print("\n[*] Phase 1: Initial Impulse (No prior history)")
    delay_1 = cerebellum.should_delay(action, urgency=0.1)
    print(f"    Delay required: {delay_1:.2f}s")
    assert delay_1 == 0.0, "[FAIL] Cerebellum unnecessarily blocked a fresh action."

    print("\n[*] Phase 2: Simulating OS Lag & Prediction Error Update")
    update_receipt = cerebellum.update(action, observed_latency=3.0, ok=True, write_receipt=False)
    print(f"    Timing Error Detected: {update_receipt.timing_error:.2f}s")
    print(f"    New Expected Latency Adjusted to: {update_receipt.next_expected_latency:.2f}s")

    print("\n[*] Phase 3: Immediate Spastic Re-fire Attempt (Ataxia simulation)")
    time.sleep(0.5)
    delay_2 = cerebellum.should_delay(action, urgency=0.1)
    print(f"    Delay required by Cerebellum: {delay_2:.2f}s")
    assert delay_2 > 0.0, "[FAIL] Cerebellum failed to dampen the spastic overcorrection."

    print("\n[*] Phase 4: Extreme Urgency Override")
    delay_3 = cerebellum.should_delay(action, urgency=0.95)
    print(f"    Delay required under high urgency: {delay_3:.2f}s")
    assert delay_3 == 0.0, "[FAIL] Cerebellum failed to yield to high-urgency sympathetic drive."

    print("\n[+] BIOLOGICAL PROOF: The Smith Predictor is functional.")
    print("    Alice can now predict the physical latency of her own body.")
    print("[+] EVENT 77 PASSED.")
    return True


if __name__ == "__main__":
    proof_of_property()
