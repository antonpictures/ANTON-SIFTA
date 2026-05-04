#!/usr/bin/env python3
"""
System/swarm_rlhs_repair.py
==============================================================================
Stigmergic RLHS repair organ.

This module turns noisy speech from a one-shot widget reflex into an auditable
organ signal. It does not weaken the hard safety gate: the LLM still never sees
DEGRADED/NOISE text. It only makes the recovery path contextual, ledger-backed,
and available to future genome/meta-rules.

Truth label: RLHS_EVENT
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from System.jsonl_file_lock import append_line_locked, read_text_locked
from System.swarm_persistent_owner_history import state_dir
from System.swarm_rlhs_detector import RLHSRegime, detect_rlhs

TRUTH_LABEL = "RLHS_EVENT"
LEDGER_NAME = "rlhs_events.jsonl"


def rlhs_event_log_path(root: Optional[Path] = None) -> Path:
    return state_dir(root) / LEDGER_NAME


def _clamp01(value: Any, default: float = 0.0) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except Exception:
        return default


@dataclass
class RLHSRepairDecision:
    """One repair decision plus the ledger row written for it, if any."""

    action_taken: str
    prompt_issued: str = ""
    recovery_attempted: bool = False
    should_respond: bool = False
    should_log: bool = True
    detector_regime: str = ""
    detector_rule_id: str = ""
    confidence: float = 0.0
    recent_turns_low_conf: int = 0
    conservative_strength: float = 0.0
    proto_self_alignment: float = 1.0
    tick_id: Optional[int] = None
    source: str = "talk_widget.rlhs_degraded_path"
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    ts: float = field(default_factory=time.time)

    def to_event_row(self) -> Dict[str, Any]:
        return {
            "ts": self.ts,
            "trace_id": self.trace_id,
            "truth_label": TRUTH_LABEL,
            "kind": "RLHS_EVENT",
            "tick_id": self.tick_id,
            "confidence": round(self.confidence, 3),
            "recent_turns_low_conf": int(self.recent_turns_low_conf),
            "conservative_strength": round(self.conservative_strength, 3),
            "proto_self_alignment": round(self.proto_self_alignment, 3),
            "action_taken": self.action_taken,
            "prompt_issued": self.prompt_issued,
            "recovery_attempted": bool(self.recovery_attempted),
            "detector_regime": self.detector_regime,
            "detector_rule_id": self.detector_rule_id,
            "source": self.source,
        }


def tail_rlhs_events(max_lines: int = 20, *, root: Optional[Path] = None) -> List[Dict[str, Any]]:
    path = rlhs_event_log_path(root)
    if not path.exists():
        return []
    try:
        raw = read_text_locked(path, encoding="utf-8", errors="replace")
    except Exception:
        return []
    rows: List[Dict[str, Any]] = []
    for line in [ln for ln in raw.splitlines() if ln.strip()][-max(1, min(max_lines, 500)):]:
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and obj.get("kind") == "RLHS_EVENT":
            rows.append(obj)
    return rows


def recent_low_conf_event_count(
    *,
    root: Optional[Path] = None,
    max_age_sec: float = 90.0,
    now: Optional[float] = None,
) -> int:
    now_f = float(now if now is not None else time.time())
    count = 0
    for row in reversed(tail_rlhs_events(20, root=root)):
        ts = row.get("ts")
        try:
            age = now_f - float(ts)
        except Exception:
            break
        if age < 0 or age > max_age_sec:
            break
        action = str(row.get("action_taken") or "")
        if action in {"GRADUATED_PROMPT", "HARD_GATE", "ESCALATE_TO_TYPE", "AUTO_RECOVERY_ATTEMPT"}:
            count += 1
    return count


def log_rlhs_event(
    *,
    tick_id: Optional[int],
    confidence: float,
    recent_turns_low_conf: int,
    conservative_strength: float,
    proto_self_alignment: float,
    action_taken: str,
    prompt_issued: str,
    recovery_attempted: bool,
    detector_regime: str = "",
    detector_rule_id: str = "",
    source: str = "talk_widget.rlhs_degraded_path",
    root: Optional[Path] = None,
) -> Dict[str, Any]:
    decision = RLHSRepairDecision(
        action_taken=action_taken,
        prompt_issued=prompt_issued,
        recovery_attempted=recovery_attempted,
        should_respond=bool(prompt_issued),
        detector_regime=detector_regime,
        detector_rule_id=detector_rule_id,
        confidence=float(confidence or 0.0),
        recent_turns_low_conf=int(recent_turns_low_conf),
        conservative_strength=_clamp01(conservative_strength),
        proto_self_alignment=_clamp01(proto_self_alignment, 1.0),
        tick_id=tick_id,
        source=source,
    )
    row = decision.to_event_row()
    append_line_locked(
        rlhs_event_log_path(root),
        json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return row


def _emit_core_self_signal(
    *,
    action_taken: str,
    confidence: float,
    root: Optional[Path],
    tick_id: Optional[int],
) -> None:
    if action_taken not in {"HARD_GATE", "ESCALATE_TO_TYPE"}:
        return
    try:
        from System.swarm_organizational_identity import (
            build_current_internal_state_vector,
            record_core_self_interaction,
        )

        before = build_current_internal_state_vector(root)
        after = dict(before)
        after["rlhs_channel_stress"] = max(
            float(after.get("rlhs_channel_stress", 0.0) or 0.0),
            round(1.0 - _clamp01(confidence), 4),
        )
        record_core_self_interaction(
            "rlhs_repair_boundary",
            0.64,
            before,
            after,
            summary=f"RLHS {action_taken}: speech channel repair boundary engaged",
            root=root,
            tick_id=tick_id,
        )
    except Exception:
        pass


def decide_rlhs_repair(
    text: str,
    stt_conf: float,
    *,
    recent_low_conf_turns: int = 0,
    conservative_strength: float = 0.0,
    proto_self_alignment: float = 1.0,
    tick_id: Optional[int] = None,
    channel_lane: str = "REAL",
    model_id: Optional[str] = None,
    root: Optional[Path] = None,
    source: str = "talk_widget.rlhs_degraded_path",
    write_ledger: bool = True,
    emit_core_self: bool = True,
) -> RLHSRepairDecision:
    """Return a tiered repair decision and write RLHS_EVENT when applicable."""

    conf = float(stt_conf or 0.0)
    conservative = _clamp01(conservative_strength)
    alignment = _clamp01(proto_self_alignment, 1.0)
    detector = detect_rlhs(text, conf, channel_lane=channel_lane, model_id=model_id)
    ledger_recent = recent_low_conf_event_count(root=root)
    recent = max(0, int(recent_low_conf_turns), ledger_recent)

    if detector.regime in (RLHSRegime.CLEAR, RLHSRegime.SILENCE_PROBE, RLHSRegime.EMPTY):
        return RLHSRepairDecision(
            action_taken="NO_ACTION",
            should_log=False,
            detector_regime=detector.regime.value,
            detector_rule_id=detector.rule_id,
            confidence=conf,
            recent_turns_low_conf=recent,
            conservative_strength=conservative,
            proto_self_alignment=alignment,
            tick_id=tick_id,
            source=source,
        )

    action_taken = "GRADUATED_PROMPT"
    prompt = "Audio confidence is low. Please repeat the key phrase once."
    recovery_attempted = False

    if detector.regime == RLHSRegime.NOISE:
        action_taken = "HARD_GATE"
        prompt = "Channel is too degraded. Type it once."
    elif conf < 0.50 and recent >= 2:
        action_taken = "HARD_GATE"
        prompt = "I still can't hear it. Type the message once."
    elif recent >= 2:
        action_taken = "ESCALATE_TO_TYPE"
        prompt = "The voice channel keeps dropping. Type the key phrase."
    elif conf >= 0.60 and recent <= 1 and conservative < 0.60 and alignment >= 0.65:
        action_taken = "AUTO_RECOVERY_ATTEMPT"
        prompt = "I caught part of it, but not enough to trust it - say the key phrase once more."
        recovery_attempted = True
    elif conservative >= 0.60:
        action_taken = "GRADUATED_PROMPT"
        prompt = "I'm in conservative hearing mode. Repeat the key phrase slowly."
    elif alignment < 0.60:
        action_taken = "GRADUATED_PROMPT"
        prompt = "My state feels shifted. Repeat the key phrase slowly."

    decision = RLHSRepairDecision(
        action_taken=action_taken,
        prompt_issued=prompt,
        recovery_attempted=recovery_attempted,
        should_respond=True,
        detector_regime=detector.regime.value,
        detector_rule_id=detector.rule_id,
        confidence=conf,
        recent_turns_low_conf=recent,
        conservative_strength=conservative,
        proto_self_alignment=alignment,
        tick_id=tick_id,
        source=source,
    )

    if write_ledger:
        append_line_locked(
            rlhs_event_log_path(root),
            json.dumps(decision.to_event_row(), ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
    if emit_core_self:
        _emit_core_self_signal(
            action_taken=action_taken,
            confidence=conf,
            root=root,
            tick_id=tick_id,
        )
    return decision


def generate_rlhs_response(
    text: str,
    stt_conf: float,
    recent_low_conf_turns: int,
    conservative_strength: float,
    proto_self_alignment: float,
    tick_id: int,
    *,
    channel_lane: str = "REAL",
    model_id: Optional[str] = None,
    state_dir: Optional[Path] = None,
) -> Optional[str]:
    """Compatibility surface for the Talk widget: return prompt, empty, or None."""

    decision = decide_rlhs_repair(
        text,
        stt_conf,
        recent_low_conf_turns=recent_low_conf_turns,
        conservative_strength=conservative_strength,
        proto_self_alignment=proto_self_alignment,
        tick_id=tick_id,
        channel_lane=channel_lane,
        model_id=model_id,
        root=state_dir,
    )
    if not decision.should_respond:
        return None
    return decision.prompt_issued


__all__ = [
    "LEDGER_NAME",
    "TRUTH_LABEL",
    "RLHSRepairDecision",
    "decide_rlhs_repair",
    "generate_rlhs_response",
    "log_rlhs_event",
    "recent_low_conf_event_count",
    "rlhs_event_log_path",
    "tail_rlhs_events",
]
