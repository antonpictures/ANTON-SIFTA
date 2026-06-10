#!/usr/bin/env python3
"""Effect-verified action wrapper — Plan A1 (r909).

Generalizes r897/r901 honest-receipt law across every effector hand:
  act → re-probe within window → receipt carries effect_verified true/false.

§6 effector immunity: Alice must not claim an external action unless a verified
receipt proves it. The 44,700 phantom YouTube skips are founding evidence for
why every hand needs this organ, not only the ad controller.

Truth label: EFFECT_VERIFIED_ACTION_V1.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
TRUTH_LABEL = "EFFECT_VERIFIED_ACTION_V1"
LEDGER = "effect_verified_actions.jsonl"
DEFAULT_VERIFY_DELAY_S = 1.5
PHANTOM_STREAK_THRESHOLD = 2


def _state(state_dir: Optional[Path | str]) -> Path:
    if state_dir is None:
        return STATE_DIR
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def enrich_effect(
    effect: Mapping[str, Any] | None,
    *,
    method: str,
    effect_verified: bool | None = None,
    effect_cleared_ms: float | None = None,
    verification_pass: int | None = None,
    organ: str = "",
    action: str = "",
) -> dict[str, Any]:
    """Attach honest §6 verification fields to any effector attempt."""
    row = dict(effect or {})
    row["method"] = str(method or row.get("method") or "unknown")
    if organ:
        row["organ"] = organ
    if action:
        row["action"] = action
    if effect_verified is not None:
        row["effect_verified"] = bool(effect_verified)
    if effect_cleared_ms is not None:
        row["effect_cleared_ms"] = round(float(effect_cleared_ms), 1)
    if verification_pass is not None:
        row["verification_pass"] = int(verification_pass)
    return row


def effect_claimed_success(effect: Mapping[str, Any] | None) -> bool:
    """True when an effect dict claims the hand succeeded (pre-verification)."""
    row = dict(effect or {})
    if row.get("ok") is True:
        return True
    reason = str(row.get("reason") or "").lower()
    phantom_markers = (
        "clicked_visible_skip_control",
        "success",
        "opened",
        "closed",
        "sent",
        "executed",
        "dispatched",
    )
    return any(marker in reason for marker in phantom_markers)


def is_phantom_effect_receipt(row: Mapping[str, Any] | None) -> bool:
    """A receipt that claims success without effect_verified true."""
    if not isinstance(row, Mapping):
        return False
    effect = row.get("effect")
    if not isinstance(effect, Mapping):
        effect = row
    if not effect_claimed_success(effect):
        return False
    if effect.get("effect_verified") is True:
        return False
    if row.get("effect_verified") is True:
        return False
    return True


@dataclass
class EffectVerifiedActionResult:
    trace_id: str
    organ: str
    action: str
    method: str
    effect: dict[str, Any]
    probe: dict[str, Any]
    effect_verified: bool
    effect_cleared_ms: float
    verification_pass: int
    phantom_streak: int = 0
    phantom_disease: bool = False
    truth_label: str = TRUTH_LABEL
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "ts": self.ts,
            "truth_label": self.truth_label,
            "organ": self.organ,
            "action": self.action,
            "method": self.method,
            "effect": self.effect,
            "probe": self.probe,
            "effect_verified": self.effect_verified,
            "effect_cleared_ms": self.effect_cleared_ms,
            "verification_pass": self.verification_pass,
            "phantom_streak": self.phantom_streak,
            "phantom_disease": self.phantom_disease,
        }


def record_effect_verified_action(
    *,
    organ: str,
    action: str,
    effect: Mapping[str, Any] | None,
    probe: Mapping[str, Any] | None = None,
    effect_verified: bool,
    method: str = "sync",
    effect_cleared_ms: float | None = None,
    verification_pass: int = 1,
    context: Mapping[str, Any] | None = None,
    state_dir: Optional[Path | str] = None,
    now: Optional[float] = None,
    trace_id: Optional[str] = None,
) -> dict[str, Any]:
    """Append one honest effect-verification receipt."""
    ts = float(now if now is not None else time.time())
    streak = count_consecutive_unverified(
        organ=organ,
        action=action,
        state_dir=state_dir,
        before_ts=ts,
    )
    if not effect_verified and effect_claimed_success(effect):
        streak += 1
    else:
        streak = 0
    enriched = enrich_effect(
        effect,
        method=method,
        effect_verified=effect_verified,
        effect_cleared_ms=effect_cleared_ms,
        verification_pass=verification_pass,
        organ=organ,
        action=action,
    )
    row = {
        "trace_id": trace_id or str(uuid.uuid4()),
        "ts": ts,
        "truth_label": TRUTH_LABEL,
        "organ": organ,
        "action": action,
        "method": method,
        "effect": enriched,
        "probe": dict(probe or {}),
        "effect_verified": bool(effect_verified),
        "effect_cleared_ms": effect_cleared_ms,
        "verification_pass": verification_pass,
        "phantom_streak": streak,
        "phantom_disease": streak >= PHANTOM_STREAK_THRESHOLD,
        "context": dict(context or {}),
    }
    base = _state(state_dir)
    base.mkdir(parents=True, exist_ok=True)
    with (base / LEDGER).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return row


def count_consecutive_unverified(
    *,
    organ: str,
    action: str,
    state_dir: Optional[Path | str] = None,
    before_ts: Optional[float] = None,
    lookback: int = 32,
) -> int:
    """Count trailing unverified success claims for organ+action."""
    base = _state(state_dir)
    path = base / LEDGER
    if not path.exists():
        return 0
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return 0
    for ln in lines[-max(1, lookback) :]:
        try:
            rows.append(json.loads(ln))
        except Exception:
            continue
    cutoff = float(before_ts) if before_ts is not None else float("inf")
    streak = 0
    for row in reversed(rows):
        ts = float(row.get("ts") or 0)
        if ts > cutoff:
            continue
        if str(row.get("organ") or "") != organ or str(row.get("action") or "") != action:
            continue
        if row.get("effect_verified") is True:
            break
        if is_phantom_effect_receipt(row):
            streak += 1
        else:
            break
    return streak


def run_sync_verified_action(
    *,
    organ: str,
    action: str,
    execute: Callable[[], Mapping[str, Any]],
    verify: Callable[[], Mapping[str, Any]],
    success_from_probe: Callable[[Mapping[str, Any], Mapping[str, Any]], bool],
    state_dir: Optional[Path | str] = None,
    verify_delay_s: float = DEFAULT_VERIFY_DELAY_S,
    method: str = "sync",
    context: Optional[Mapping[str, Any]] = None,
    sleep_fn: Callable[[float], None] | None = None,
) -> EffectVerifiedActionResult:
    """Synchronous wrapper: execute → wait → verify → honest receipt."""
    started = time.time()
    effect = dict(execute() or {})
    if not effect_claimed_success(effect):
        row = record_effect_verified_action(
            organ=organ,
            action=action,
            effect=effect,
            probe={},
            effect_verified=False,
            method=method,
            effect_cleared_ms=0.0,
            verification_pass=0,
            context=context,
            state_dir=state_dir,
            now=time.time(),
        )
        return EffectVerifiedActionResult(
            trace_id=str(row.get("trace_id") or ""),
            organ=organ,
            action=action,
            method=method,
            effect=dict(row.get("effect") or effect),
            probe={},
            effect_verified=False,
            effect_cleared_ms=0.0,
            verification_pass=0,
            phantom_streak=int(row.get("phantom_streak") or 0),
            phantom_disease=bool(row.get("phantom_disease")),
            ts=float(row.get("ts") or time.time()),
        )

    sleeper = sleep_fn or time.sleep
    sleeper(max(0.0, float(verify_delay_s)))
    probe = dict(verify() or {})
    verified = bool(success_from_probe(effect, probe))
    elapsed_ms = max(0.0, (time.time() - started) * 1000.0)
    row = record_effect_verified_action(
        organ=organ,
        action=action,
        effect=effect,
        probe=probe,
        effect_verified=verified,
        method=method,
        effect_cleared_ms=elapsed_ms,
        verification_pass=1,
        context=context,
        state_dir=state_dir,
        now=time.time(),
    )
    return EffectVerifiedActionResult(
        trace_id=str(row.get("trace_id") or ""),
        organ=organ,
        action=action,
        method=method,
        effect=dict(row.get("effect") or effect),
        probe=probe,
        effect_verified=verified,
        effect_cleared_ms=elapsed_ms,
        verification_pass=1,
        phantom_streak=int(row.get("phantom_streak") or 0),
        phantom_disease=bool(row.get("phantom_disease")),
        ts=float(row.get("ts") or time.time()),
    )


def complete_async_verified_action(
    *,
    organ: str,
    action: str,
    initial_effect: Mapping[str, Any] | None,
    probe: Mapping[str, Any] | None,
    success_from_probe: Callable[[Mapping[str, Any], Mapping[str, Any]], bool],
    started_at: float,
    method: str = "async",
    verification_pass: int = 1,
    context: Optional[Mapping[str, Any]] = None,
    state_dir: Optional[Path | str] = None,
) -> EffectVerifiedActionResult:
    """Finish an async hand after the deferred probe returns."""
    effect = dict(initial_effect or {})
    probe_row = dict(probe or {})
    verified = bool(success_from_probe(effect, probe_row))
    elapsed_ms = max(0.0, (time.time() - float(started_at)) * 1000.0)
    row = record_effect_verified_action(
        organ=organ,
        action=action,
        effect=effect,
        probe=probe_row,
        effect_verified=verified,
        method=method,
        effect_cleared_ms=elapsed_ms,
        verification_pass=verification_pass,
        context=context,
        state_dir=state_dir,
        now=time.time(),
    )
    return EffectVerifiedActionResult(
        trace_id=str(row.get("trace_id") or ""),
        organ=organ,
        action=action,
        method=method,
        effect=dict(row.get("effect") or effect),
        probe=probe_row,
        effect_verified=verified,
        effect_cleared_ms=elapsed_ms,
        verification_pass=verification_pass,
        phantom_streak=int(row.get("phantom_streak") or 0),
        phantom_disease=bool(row.get("phantom_disease")),
        ts=float(row.get("ts") or time.time()),
    )


__all__ = [
    "TRUTH_LABEL",
    "LEDGER",
    "DEFAULT_VERIFY_DELAY_S",
    "PHANTOM_STREAK_THRESHOLD",
    "EffectVerifiedActionResult",
    "complete_async_verified_action",
    "count_consecutive_unverified",
    "effect_claimed_success",
    "enrich_effect",
    "is_phantom_effect_receipt",
    "record_effect_verified_action",
    "run_sync_verified_action",
]