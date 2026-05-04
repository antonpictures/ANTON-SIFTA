#!/usr/bin/env python3
"""
System/swarm_motor_cortex.py
==============================================================================
Stigmergic Motor Cortex Organ.

This module has two compatible surfaces:

1. Legacy autonomic body language (`emit`, `current_bpm`, `recent_pulses`) used
   by the GUI/boot path for heartbeat-style motor pulses.
2. Semantic motor actions (`propose_motor_action`, `execute_semantic_typing`)
   that translate intent such as "click search bar" into auditable OS actions.

The design keeps external restrictions minimal. Ordinary action is governed by
Alice's internal organs and receipts. The hard perimeter blocks only actions
that would plausibly damage the local body, owner boundary, repo, credentials,
or irreversible external state.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from System.jsonl_file_lock import append_line_locked, read_text_locked
from System.swarm_persistent_owner_history import state_dir

TRUTH_LABEL = "MOTOR_ACTION"
ACTION_LOG_NAME = "motor_cortex_log.jsonl"
PULSE_LOG_NAME = "motor_pulses.jsonl"
HEARTBEAT_NAME = "clinical_heartbeat.json"

LOW_CONFIDENCE_FLOOR = 0.40
MEDIUM_CONFIDENCE_FLOOR = 0.72
TEXT_ENTRY_CONFIDENCE_FLOOR = 0.80
EXECUTE_ENV = "SIFTA_MOTOR_CORTEX_EXECUTE"


def motor_log_path(root: Optional[Path] = None) -> Path:
    return state_dir(root) / ACTION_LOG_NAME


def motor_pulse_path(root: Optional[Path] = None) -> Path:
    return state_dir(root) / PULSE_LOG_NAME


def _heartbeat_path(root: Optional[Path] = None) -> Path:
    return state_dir(root) / HEARTBEAT_NAME


# ── Legacy body-language API ─────────────────────────────────────────────────

@dataclass(frozen=True)
class Pulse:
    kind: str
    dock_bounces: int
    dock_gap_ms: int
    led_blink_ms: int
    sign_language: str


_VOCAB: Dict[str, Pulse] = {
    "heartbeat":   Pulse("heartbeat",   1, 0,   160, "single soft pulse"),
    "hello":       Pulse("hello",       2, 120,   0, "two-bounce greeting"),
    "thinking":    Pulse("thinking",    1, 0,     0, "single slow bounce"),
    "speak_start": Pulse("speak_start", 1, 0,    80, "wink as voice opens"),
    "tool_call":   Pulse("tool_call",   3, 90,    0, "triple-bounce burst"),
    "alarm":       Pulse("alarm",       5, 70,  400, "sustained alarm"),
    "sleep":       Pulse("sleep",       0, 0,   600, "long slow wink"),
}


def vocabulary() -> List[str]:
    return sorted(_VOCAB)


def current_bpm(*, root: Optional[Path] = None) -> int:
    """Resolve a target BPM from clinical_heartbeat.json; default is calm 12."""
    path = _heartbeat_path(root)
    if not path.exists():
        return 12
    try:
        data = json.loads(read_text_locked(path, encoding="utf-8", errors="replace") or "{}")
    except Exception:
        return 12

    rhythm = str(data.get("clinical_rhythm") or "").upper()
    vitals = data.get("vital_signs") or {}
    drive = str(vitals.get("dopamine_drive") or "").upper()
    da = _safe_float(vitals.get("dopamine_concentration"), 100.0)
    se = _safe_float(vitals.get("serotonin_dominance"), 0.6)

    if "HYPOTONIC" in rhythm or "STRESS" in rhythm or se < 0.3:
        return 30
    if "HYPER" in rhythm or da > 140:
        return 24
    if "ACTIVE" in drive or "ENGAGED" in drive:
        return 18
    return 12


def heart_period_s(*, root: Optional[Path] = None) -> float:
    return 60.0 / max(6, current_bpm(root=root))


def emit(kind: str = "heartbeat", *, source: str = "motor_cortex", root: Optional[Path] = None) -> Dict[str, Any]:
    """Append one motor pulse row and return it."""
    if kind not in _VOCAB:
        raise ValueError(f"unknown motor pulse kind {kind!r}. known: {vocabulary()}")
    pulse = _VOCAB[kind]
    row = {
        "ts": time.time(),
        "kind": pulse.kind,
        "truth_label": "MOTOR_PULSE",
        "bpm": current_bpm(root=root),
        "dock_bounces": pulse.dock_bounces,
        "dock_gap_ms": pulse.dock_gap_ms,
        "led_blink_ms": pulse.led_blink_ms,
        "sign_language": pulse.sign_language,
        "source": source,
    }
    append_line_locked(
        motor_pulse_path(root),
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return row


def recent_pulses(n: int = 5, *, root: Optional[Path] = None) -> List[Dict[str, Any]]:
    path = motor_pulse_path(root)
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    for line in read_text_locked(path, encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out[-max(1, int(n)):]


def bounce_dock_qt(window: Any, kind: str = "heartbeat", *, source: str = "motor_cortex") -> Dict[str, Any]:
    """Emit a pulse and bounce the Dock when called inside a Qt GUI."""
    row = emit(kind, source=source)
    if window is None:
        return row
    try:
        from PyQt6.QtCore import QTimer
        from PyQt6.QtWidgets import QApplication
    except Exception:
        return row

    pulse = _VOCAB[kind]
    if pulse.dock_bounces <= 0:
        return row

    def _one_bounce() -> None:
        try:
            QApplication.alert(window, 0)
        except Exception:
            pass

    _one_bounce()
    for i in range(1, pulse.dock_bounces):
        QTimer.singleShot(i * pulse.dock_gap_ms, _one_bounce)
    return row


# ── Semantic Motor Cortex ────────────────────────────────────────────────────

def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize(text: Any) -> str:
    return " ".join(str(text or "").casefold().replace("_", " ").replace("-", " ").split())


def _contains_any(text: str, words: Iterable[str]) -> bool:
    return any(w in text for w in words)


@dataclass
class SemanticTargetResolution:
    semantic_target: str
    resolved_coordinates: Optional[Tuple[int, int]] = None
    confidence: float = 0.0
    method: str = "unresolved"
    matched_label: str = ""
    visual_context: Dict[str, Any] = field(default_factory=dict)

    def to_row(self) -> Dict[str, Any]:
        return {
            "semantic_target": self.semantic_target,
            "resolved_coordinates": list(self.resolved_coordinates) if self.resolved_coordinates else None,
            "confidence": round(float(self.confidence), 3),
            "method": self.method,
            "matched_label": self.matched_label,
            "visual_context": dict(self.visual_context),
        }


@dataclass
class MotorActionDecision:
    action_type: str
    semantic_target: str
    target_window: str
    target_app: str
    confidence: float
    conservative_strength: float
    risk_tier: str
    execution_status: str
    resolved_coordinates: Optional[Tuple[int, int]] = None
    visual_confirmation_required: Sequence[str] = field(default_factory=tuple)
    hard_perimeter_reason: str = ""
    owner_go_required: bool = False
    owner_go_present: bool = False
    stgm_cost: float = 0.0
    semantic_resolution: Dict[str, Any] = field(default_factory=dict)
    tick_id: Optional[int] = None
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    ts: float = field(default_factory=time.time)

    @property
    def permitted(self) -> bool:
        return self.execution_status in {"PERMITTED", "DRY_RUN", "EXECUTED"}

    def to_row(self) -> Dict[str, Any]:
        return {
            "ts": self.ts,
            "trace_id": self.trace_id,
            "tick_id": self.tick_id,
            "kind": TRUTH_LABEL,
            "truth_label": TRUTH_LABEL,
            "schema": "SIFTA_MOTOR_ACTION_V2",
            "action_type": self.action_type.upper(),
            "semantic_target": self.semantic_target,
            "resolved_coordinates": list(self.resolved_coordinates) if self.resolved_coordinates else None,
            "target_window": self.target_window,
            "target_app": self.target_app,
            "confidence": round(float(self.confidence), 3),
            "conservative_strength": round(float(self.conservative_strength), 3),
            "risk_tier": self.risk_tier,
            "visual_confirmation_required": list(self.visual_confirmation_required),
            "execution_status": self.execution_status,
            "permitted": self.permitted,
            "hard_perimeter_reason": self.hard_perimeter_reason,
            "owner_go_required": self.owner_go_required,
            "owner_go_present": self.owner_go_present,
            "stgm_cost": round(float(self.stgm_cost), 6),
            "semantic_resolution": dict(self.semantic_resolution),
            "provenance": "SIFTA_MOTOR_CORTEX_SEMANTIC_TARGETING_V2",
        }


def resolve_semantic_target(
    semantic_target: str,
    *,
    candidates: Optional[Sequence[Dict[str, Any]]] = None,
    fallback_coordinates: Optional[Tuple[int, int]] = None,
    visual_context: Optional[Dict[str, Any]] = None,
) -> SemanticTargetResolution:
    """Resolve human-style target text into coordinates without leaking vision context."""
    target = _normalize(semantic_target)
    best: Optional[Dict[str, Any]] = None
    best_score = 0.0

    for item in candidates or ():
        labels = [
            item.get("label"),
            item.get("name"),
            item.get("role"),
            item.get("semantic_target"),
            item.get("text"),
        ]
        haystack = _normalize(" ".join(str(x or "") for x in labels))
        if not haystack:
            continue
        target_tokens = set(target.split())
        hay_tokens = set(haystack.split())
        overlap = len(target_tokens & hay_tokens) / max(1, len(target_tokens))
        substring = 1.0 if target and (target in haystack or haystack in target) else 0.0
        score = max(overlap, substring) * _safe_float(item.get("confidence"), 1.0)
        if score > best_score:
            best = item
            best_score = score

    if best:
        coords = best.get("coordinates") or best.get("center") or best.get("xy")
        resolved = _coerce_xy(coords)
        return SemanticTargetResolution(
            semantic_target=semantic_target,
            resolved_coordinates=resolved,
            confidence=max(0.0, min(1.0, best_score)),
            method="candidate_match",
            matched_label=str(best.get("label") or best.get("name") or best.get("role") or ""),
            visual_context=visual_context or {},
        )

    if fallback_coordinates is not None:
        return SemanticTargetResolution(
            semantic_target=semantic_target,
            resolved_coordinates=_coerce_xy(fallback_coordinates),
            confidence=0.55,
            method="fallback_coordinates",
            visual_context=visual_context or {},
        )

    return SemanticTargetResolution(
        semantic_target=semantic_target,
        resolved_coordinates=None,
        confidence=0.0,
        method="unresolved",
        visual_context=visual_context or {},
    )


def _coerce_xy(value: Any) -> Optional[Tuple[int, int]]:
    if value is None:
        return None
    try:
        x, y = value[0], value[1]
        return int(round(float(x))), int(round(float(y)))
    except Exception:
        return None


def assess_motor_risk(
    action_type: str,
    semantic_target: str,
    active_window: str,
    active_app: str,
    *,
    text: str = "",
) -> str:
    """Classify action risk with the hard perimeter kept intentionally small."""
    action = _normalize(action_type)
    target = _normalize(semantic_target)
    appwin = _normalize(f"{active_app} {active_window}")
    payload = _normalize(text)
    combined = f"{action} {target} {appwin} {payload}"

    hard_terms = {
        "delete critical", "delete repo", "rm rf", "factory reset", "erase disk",
        "credential", "private key", "keychain", "login item", "security setting",
        "kill sifta", "quit sifta", "shutdown body", "disable safety",
        "send money", "spend real money", "publish", "post externally",
        "send email", "send sms", "send whatsapp",
    }
    if _contains_any(combined, hard_terms):
        return "HARD_PERIMETER"

    terminal_like = _contains_any(appwin, {"terminal", "iterm", "shell", "console"})
    system_like = _contains_any(appwin, {"system settings", "preferences", "activity monitor"})
    finder_like = "finder" in appwin
    external_post = _contains_any(target, {"post button", "send button", "publish button", "share button"})

    if terminal_like and action in {"type", "keypress", "paste"}:
        return "HIGH"
    if system_like or finder_like or external_post:
        return "MEDIUM"
    if action in {"type", "paste"}:
        return "MEDIUM"
    return "LOW"


def visual_confirmation_required(risk_tier: str, action_type: str) -> Tuple[str, ...]:
    tier = str(risk_tier or "LOW").upper()
    action = _normalize(action_type)
    if tier == "HARD_PERIMETER":
        return ("owner_go",)
    if tier == "HIGH":
        return ("before", "after")
    if tier == "MEDIUM" or action in {"type", "paste"}:
        return ("before", "after")
    return ("before",)


def _perimeter_reason(risk_tier: str, *, owner_go: bool) -> str:
    if risk_tier == "HARD_PERIMETER" and not owner_go:
        return "hard perimeter requires explicit owner GO for irreversible body/owner/repo/external action"
    return ""


def propose_motor_action(
    action_type: str,
    semantic_target: str,
    active_window: str,
    active_app: str,
    confidence: float,
    conservative_strength: float,
    root: Optional[Path] = None,
    *,
    candidates: Optional[Sequence[Dict[str, Any]]] = None,
    fallback_coordinates: Optional[Tuple[int, int]] = None,
    resolved_coordinates: Optional[Tuple[int, int]] = None,
    visual_context: Optional[Dict[str, Any]] = None,
    owner_go: bool = False,
    text: str = "",
    stgm_cost: float = 0.0,
    tick_id: Optional[int] = None,
    write_ledger: bool = True,
) -> MotorActionDecision:
    """Create an auditable semantic motor decision. This does not execute."""
    resolution = resolve_semantic_target(
        semantic_target,
        candidates=candidates,
        fallback_coordinates=resolved_coordinates or fallback_coordinates,
        visual_context=visual_context,
    )
    if resolution.method == "candidate_match":
        effective_conf = min(float(confidence), resolution.confidence)
    else:
        # Explicit caller-provided coordinates are execution detail; the caller's
        # visual confidence remains the primary confidence signal.
        effective_conf = float(confidence)

    risk_tier = assess_motor_risk(
        action_type,
        semantic_target,
        active_window,
        active_app,
        text=text,
    )
    required = visual_confirmation_required(risk_tier, action_type)
    perimeter = _perimeter_reason(risk_tier, owner_go=owner_go)

    status = "PERMITTED"
    if perimeter:
        status = "BLOCKED_BY_PERIMETER"
    elif risk_tier == "HIGH" and not owner_go:
        status = "BLOCKED_BY_RISK"
    elif risk_tier == "MEDIUM" and (conservative_strength > 0.70 or effective_conf < TEXT_ENTRY_CONFIDENCE_FLOOR):
        status = "BLOCKED_BY_RISK"
    elif risk_tier == "LOW" and effective_conf < LOW_CONFIDENCE_FLOOR:
        status = "ABORTED_LOW_CONFIDENCE"

    decision = MotorActionDecision(
        action_type=action_type,
        semantic_target=semantic_target,
        target_window=active_window,
        target_app=active_app,
        confidence=effective_conf,
        conservative_strength=conservative_strength,
        risk_tier=risk_tier,
        execution_status=status,
        resolved_coordinates=resolution.resolved_coordinates,
        visual_confirmation_required=required,
        hard_perimeter_reason=perimeter,
        owner_go_required=bool(risk_tier in {"HARD_PERIMETER", "HIGH"}),
        owner_go_present=bool(owner_go),
        stgm_cost=stgm_cost,
        semantic_resolution=resolution.to_row(),
        tick_id=tick_id,
    )

    if write_ledger:
        append_line_locked(
            motor_log_path(root),
            json.dumps(decision.to_row(), ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return decision


def execute_motor_action(
    decision: MotorActionDecision,
    *,
    executor: Optional[Any] = None,
    root: Optional[Path] = None,
    execute: Optional[bool] = None,
) -> MotorActionDecision:
    """Execute a permitted action through a caller-provided executor or env-gated OS path."""
    should_execute = bool(os.environ.get(EXECUTE_ENV) == "1") if execute is None else bool(execute)
    status = decision.execution_status

    if not decision.permitted:
        status = decision.execution_status
    elif not should_execute and executor is None:
        status = "DRY_RUN"
    else:
        try:
            if executor is not None:
                executor(decision)
            else:
                _execute_with_osascript(decision)
            status = "EXECUTED"
        except Exception as exc:
            status = "EXECUTION_FAILED"
            decision.hard_perimeter_reason = f"execution error: {exc}"

    executed = MotorActionDecision(
        action_type=decision.action_type,
        semantic_target=decision.semantic_target,
        target_window=decision.target_window,
        target_app=decision.target_app,
        confidence=decision.confidence,
        conservative_strength=decision.conservative_strength,
        risk_tier=decision.risk_tier,
        execution_status=status,
        resolved_coordinates=decision.resolved_coordinates,
        visual_confirmation_required=decision.visual_confirmation_required,
        hard_perimeter_reason=decision.hard_perimeter_reason,
        owner_go_required=decision.owner_go_required,
        owner_go_present=decision.owner_go_present,
        stgm_cost=decision.stgm_cost,
        semantic_resolution=decision.semantic_resolution,
        tick_id=decision.tick_id,
        trace_id=decision.trace_id,
    )

    append_line_locked(
        motor_log_path(root),
        json.dumps(executed.to_row(), ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return executed


def _execute_with_osascript(decision: MotorActionDecision) -> None:
    action = decision.action_type.upper()
    if action == "CLICK" and decision.resolved_coordinates:
        x, y = decision.resolved_coordinates
        script = (
            'tell application "System Events"\n'
            f"  click at {{{x}, {y}}}\n"
            "end tell"
        )
    elif action in {"TYPE", "PASTE"}:
        text = str(decision.semantic_resolution.get("text") or "")
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        script = f'tell application "System Events" to keystroke "{escaped}"'
    else:
        raise ValueError(f"unsupported OS execution action {action!r}")
    subprocess.run(["osascript", "-e", script], check=True, capture_output=True, timeout=5)


def execute_semantic_typing(
    text: str,
    active_window: str,
    active_app: str,
    confidence: float,
    conservative_strength: float,
    root: Optional[Path] = None,
    *,
    owner_go: bool = False,
    execute: Optional[bool] = None,
) -> bool:
    """Compatibility helper. Actual typing requires SIFTA_MOTOR_CORTEX_EXECUTE=1 or execute=True."""
    decision = propose_motor_action(
        action_type="TYPE",
        semantic_target="text field",
        active_window=active_window,
        active_app=active_app,
        confidence=confidence,
        conservative_strength=conservative_strength,
        root=root,
        owner_go=owner_go,
        text=text,
    )
    decision.semantic_resolution["text"] = text
    executed = execute_motor_action(decision, root=root, execute=execute)
    return executed.execution_status == "EXECUTED"


def recent_motor_actions(n: int = 10, *, root: Optional[Path] = None) -> List[Dict[str, Any]]:
    path = motor_log_path(root)
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for line in read_text_locked(path, encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows[-max(1, int(n)):]


def summary_for_prompt(*, root: Optional[Path] = None) -> str:
    rows = recent_motor_actions(1, root=root)
    if not rows:
        return ""
    row = rows[-1]
    return (
        "MOTOR CORTEX:\n"
        f"- last_action={row.get('action_type')} target={row.get('semantic_target')} "
        f"status={row.get('execution_status')} risk={row.get('risk_tier')}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(prog="swarm_motor_cortex")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("tick")
    sub.add_parser("bpm")
    emit_p = sub.add_parser("emit")
    emit_p.add_argument("kind", choices=vocabulary())
    recent_p = sub.add_parser("recent")
    recent_p.add_argument("n", nargs="?", type=int, default=5)
    args = parser.parse_args()

    if args.cmd == "bpm":
        print(f"current_bpm = {current_bpm()}  (period {heart_period_s():.2f}s)")
        return 0
    if args.cmd == "emit":
        print(json.dumps(emit(args.kind, source="cli"), sort_keys=True))
        return 0
    if args.cmd == "recent":
        for row in recent_pulses(args.n):
            print(json.dumps(row, sort_keys=True))
        return 0

    print(json.dumps(emit("heartbeat", source="cli"), sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
