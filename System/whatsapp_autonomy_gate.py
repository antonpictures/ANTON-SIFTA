#!/usr/bin/env python3
"""
System/whatsapp_autonomy_gate.py
Bounded WhatsApp autonomy for Alice.

This is the social-distance organ: Alice may propose or send only when
consent, relevance, timing, urgency, and repetition state agree. The math is
a bounded Gaussian attention field, not persuasion machinery.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import math
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_AUTONOMY_LEDGER = _STATE / "whatsapp_autonomy_gate.jsonl"
_BRIDGE_LEDGER = _STATE / "whatsapp_bridge_trace.jsonl"


def gaussian(x: float, mu: float, sigma: float) -> float:
    """Bounded Gaussian attraction score in [0, 1]."""
    sigma = max(float(sigma), 1e-9)
    return math.exp(-((float(x) - float(mu)) ** 2) / (2.0 * sigma ** 2))


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def attraction_score(
    *,
    consent: bool,
    user_replied_recently: float,
    emotional_warmth: float,
    urgency: float,
    topic_match: float,
    repetition: float,
    time_since_last_msg_min: float,
) -> float:
    """Continuous social-attraction field used before any autonomous send."""
    if not consent:
        return 0.0

    timing = gaussian(time_since_last_msg_min, mu=180.0, sigma=120.0)
    score = (
        0.25 * _clip01(user_replied_recently)
        + 0.20 * _clip01(emotional_warmth)
        + 0.20 * _clip01(topic_match)
        + 0.20 * _clip01(urgency)
        + 0.15 * timing
        - 0.35 * _clip01(repetition)
    )
    return _clip01(score)


def should_message(score: float, *, user_initiated: bool, emergency: bool) -> bool:
    """Decision gate. Emergency overrides scoring; everything else is bounded."""
    if emergency:
        return True
    if user_initiated and score > 0.35:
        return True
    return score > 0.72


@dataclass
class AutonomyInputs:
    consent: bool
    user_replied_recently: float = 0.0
    emotional_warmth: float = 0.5
    urgency: float = 0.0
    topic_match: float = 0.5
    repetition: float = 0.0
    time_since_last_msg_min: float = 9999.0
    user_initiated: bool = False
    emergency: bool = False
    group_target: bool = False
    group_consent: bool = False


@dataclass
class AutonomyDecision:
    should_send: bool
    score: float
    status: str
    reason: str
    timing_attraction: float
    inputs: Dict[str, Any]
    decision_hash: str


def evaluate_autonomy(inputs: AutonomyInputs) -> AutonomyDecision:
    """Evaluate Alice's WhatsApp autonomy without causing any external action."""
    score = attraction_score(
        consent=inputs.consent,
        user_replied_recently=inputs.user_replied_recently,
        emotional_warmth=inputs.emotional_warmth,
        urgency=inputs.urgency,
        topic_match=inputs.topic_match,
        repetition=inputs.repetition,
        time_since_last_msg_min=inputs.time_since_last_msg_min,
    )
    timing = gaussian(inputs.time_since_last_msg_min, mu=180.0, sigma=120.0)

    status = "ALLOW_SEND" if should_message(
        score,
        user_initiated=inputs.user_initiated,
        emergency=inputs.emergency,
    ) else "SILENCE_LOW_ATTRACTION"
    reason = "bounded_attraction_passed" if status == "ALLOW_SEND" else "low_attraction_or_boundary"

    if not inputs.consent:
        status = "SILENCE_NO_CONSENT"
        reason = "contact_or_owner_has_not_granted_autonomous_whatsapp_consent"
    elif inputs.group_target and not inputs.group_consent:
        status = "SILENCE_GROUP_BOUNDARY"
        reason = "group_messages_need_explicit_group_consent"
    elif inputs.repetition >= 0.85 and not inputs.emergency:
        status = "SILENCE_REPETITION_REFRACTORY"
        reason = "message_is_too_similar_to_recent_outbound_text"

    should_send_flag = status == "ALLOW_SEND"
    payload = {
        "score": round(score, 6),
        "status": status,
        "reason": reason,
        "inputs": asdict(inputs),
    }
    decision_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return AutonomyDecision(
        should_send=should_send_flag,
        score=score,
        status=status,
        reason=reason,
        timing_attraction=timing,
        inputs=asdict(inputs),
        decision_hash=decision_hash,
    )


def _iter_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line.startswith("{"):
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        return []
    return rows


def _similarity(a: str, b: str) -> float:
    a = " ".join((a or "").casefold().split())
    b = " ".join((b or "").casefold().split())
    if not a or not b:
        return 0.0
    return float(difflib.SequenceMatcher(None, a, b).ratio())


def infer_repetition_and_timing(
    *,
    target: str,
    text: str,
    now: Optional[float] = None,
    bridge_ledger: Optional[Path] = None,
) -> Dict[str, float]:
    """Infer repetition and spacing from local outbound receipts only."""
    t = time.time() if now is None else float(now)
    bridge_ledger = _BRIDGE_LEDGER if bridge_ledger is None else bridge_ledger
    target_norm = (target or "").casefold().strip()
    last_ts = 0.0
    repetition = 0.0
    for row in _iter_jsonl(bridge_ledger):
        if row.get("event_kind") != "WHATSAPP_SEND_ATTEMPT":
            continue
        row_target = str(row.get("resolved_jid") or row.get("target") or "").casefold()
        if target_norm and target_norm not in row_target and row_target not in target_norm:
            continue
        row_ts = float(row.get("ts") or 0.0)
        if row_ts > last_ts:
            last_ts = row_ts
        repetition = max(repetition, _similarity(text, str(row.get("text") or "")))
    if last_ts <= 0:
        time_since = 9999.0
    else:
        time_since = max(0.0, (t - last_ts) / 60.0)
    return {
        "time_since_last_msg_min": time_since,
        "repetition": _clip01(repetition),
    }


def log_decision(decision: AutonomyDecision, *, target: str, text_hash: str) -> Dict[str, Any]:
    """Append a non-effector autonomy decision receipt."""
    row = {
        "event_kind": "WHATSAPP_AUTONOMY_DECISION",
        "schema": "SIFTA_WHATSAPP_AUTONOMY_GATE_V1",
        "ts": time.time(),
        "target": target,
        "text_hash": text_hash,
        **asdict(decision),
    }
    _AUTONOMY_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    try:
        from System.jsonl_file_lock import append_line_locked
        append_line_locked(_AUTONOMY_LEDGER, json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        with _AUTONOMY_LEDGER.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def summary_for_alice(limit: int = 3) -> str:
    rows = list(_iter_jsonl(_AUTONOMY_LEDGER))[-limit:]
    lines = [
        "WHATSAPP AUTONOMY:",
        "- I may send autonomously only through bounded attraction: consent + relevance + timing + urgency - repetition.",
        "- No consent or group boundary means silence, not a message.",
    ]
    for row in rows:
        lines.append(
            f"- last_decision={row.get('status')} score={float(row.get('score', 0.0)):.2f} "
            f"reason={row.get('reason')} hash={str(row.get('decision_hash', ''))[:12]}"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    sample = AutonomyInputs(
        consent=True,
        user_replied_recently=0.8,
        emotional_warmth=0.7,
        urgency=0.2,
        topic_match=0.9,
        repetition=0.0,
        time_since_last_msg_min=180.0,
        user_initiated=False,
    )
    print(json.dumps(asdict(evaluate_autonomy(sample)), indent=2))
