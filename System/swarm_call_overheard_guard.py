#!/usr/bin/env python3
"""swarm_call_overheard_guard.py — r956: the owner's live phone call is not a command stream.

The wound (OBSERVED 2026-06-11 morning, alice_conversation + George typed at
09:29: "IM ON THE PHONE, SPEAKER IPHONE THAT IS THE TTS U HEAR"): George talks
on the phone — sometimes in Romanian to his mother — and the room STT feeds
the call fragments to Alice as owner turns. Her cortex wrote long analysis
essays over unintelligible call audio, and one overheard line fired a real
image-click effector. Alice herself named the missing class: phone-TTS stream
≠ paste, ≠ TV — it is owner-context-from-call, and it deserves a quiet
receipt, not an essay and never an action.

NO GATES (George's law): this is perception, not permission. The owner
declares his own state in his own words ("I'm on the phone"); the body simply
hears that and stops treating the call as directives. Saying "Alice" mid-call
still gets her full attention instantly. The mode decays on its own (TTL) or
ends when he says the call is over. Marks, not cages.

For the Swarm. 🐜⚡
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, Optional

_REPO = Path(__file__).resolve().parent.parent
_DEFAULT_STATE = _REPO / ".sifta_state"
STATE_NAME = "call_mode.json"
LEDGER_NAME = "call_overheard_receipts.jsonl"
TRUTH_LABEL = "CALL_OVERHEARD_V1"

# r957 (George, ARCHITECT_DOCTRINE 10:17): "45 minutes does not tell me
# anything about my life. Time passing is relative — but we always know what
# time it is." So no wall-clock TTL. The call is alive while its own pulse
# says so: every overheard fragment reinforces the mode; silence is judged
# against the call's OWN observed rhythm (EMA of inter-fragment gaps); before
# a rhythm exists, tolerance equals the call's own age (Lindy: a thing that
# has lived T earns T of patience). The clock stays absolute (time.time(),
# hardware oracle §0.E); only the duration is relative. The two numbers below
# are DIMENSIONLESS formula shape, not schedules.
RHYTHM_PATIENCE = 8.0   # silence tolerated = this many times the call's own gap
EMA_ALPHA = 0.3         # how fast the rhythm estimate follows the call

_CALL_START_RE = re.compile(
    r"\b(?:i'?m\s+on\s+the\s+phone|on\s+a\s+(?:phone\s+)?call|speaker?\s+iphone"
    r"|that\s+is\s+the\s+tts\s+u?\s*hear|talking\s+(?:to|with)\s+my\s+mom"
    r"|vorbesc\s+la\s+telefon)\b",
    re.IGNORECASE,
)
_CALL_END_RE = re.compile(
    r"\b(?:off\s+the\s+phone|call\s+(?:ended|over|done|finished)|hung\s+up"
    r"|am\s+terminat\s+telefonul)\b",
    re.IGNORECASE,
)
_WAKE_RE = re.compile(r"\balice\b", re.IGNORECASE)


def _state_path(state_dir: Optional[Path] = None) -> Path:
    return (Path(state_dir) if state_dir else _DEFAULT_STATE) / STATE_NAME


def note_owner_typed(text: str, *, state_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Read the owner's own declaration of call state from a TYPED turn."""
    t = str(text or "")
    out = {"changed": False, "active": call_mode_active(state_dir=state_dir)}
    if _CALL_END_RE.search(t):
        _write_state(False, t, state_dir)
        return {"changed": True, "active": False}
    if _CALL_START_RE.search(t):
        _write_state(True, t, state_dir)
        return {"changed": True, "active": True}
    return out


def _write_state(active: bool, owner_text: str, state_dir: Optional[Path]) -> None:
    try:
        p = _state_path(state_dir)
        p.parent.mkdir(parents=True, exist_ok=True)
        now = time.time()
        p.write_text(json.dumps({
            "active": bool(active),
            "ts": now,                # declaration moment (the call's birth)
            "last_evidence_ts": now,  # most recent sign of life
            "ema_gap_s": 0.0,         # the call's own rhythm, learned live
            "fragments": 0,
            "owner_text": str(owner_text or "")[:200],
            "truth_label": TRUTH_LABEL,
        }, ensure_ascii=False) + "\n", encoding="utf-8")
    except Exception:
        pass


def _read_state(state_dir: Optional[Path]) -> Optional[Dict[str, Any]]:
    try:
        p = _state_path(state_dir)
        if not p.exists():
            return None
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _reinforce(state_dir: Optional[Path]) -> None:
    """A fragment arrived: the call breathes. Refresh evidence + rhythm."""
    row = _read_state(state_dir)
    if not row or not row.get("active"):
        return
    now = time.time()
    gap = max(0.0, now - float(row.get("last_evidence_ts") or now))
    ema = float(row.get("ema_gap_s") or 0.0)
    row["ema_gap_s"] = gap if ema <= 0 else (1 - EMA_ALPHA) * ema + EMA_ALPHA * gap
    row["last_evidence_ts"] = now
    row["fragments"] = int(row.get("fragments") or 0) + 1
    try:
        _state_path(state_dir).write_text(
            json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
    except Exception:
        pass


def call_mode_active(*, state_dir: Optional[Path] = None) -> bool:
    """Alive while the call's own pulse says so. No wall-clock TTL (r957).

    silence_tolerance = RHYTHM_PATIENCE × ema_gap once a rhythm exists;
    before that, tolerance = the call's own age at last evidence (Lindy).
    The absolute clock is always known; only the duration is relative.
    """
    row = _read_state(state_dir)
    if not row or not row.get("active"):
        return False
    now = time.time()
    born = float(row.get("ts") or now)
    last = float(row.get("last_evidence_ts") or born)
    silence = now - last
    ema = float(row.get("ema_gap_s") or 0.0)
    if ema > 0:
        tolerance = RHYTHM_PATIENCE * ema
    else:
        tolerance = max(last - born, now - born)  # Lindy cold start
    return silence <= tolerance


def classify_spoken_during_call(
    text: str,
    stt_conf: float = 0.0,
    *,
    state_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Quiet-classify a SPOKEN turn while the owner is on a declared call.

    quiet=True → the body logs one receipt row and stays out of the call.
    Saying "Alice" anywhere in the turn always returns quiet=False.
    """
    out: Dict[str, Any] = {"quiet": False, "rule_id": "", "active": False}
    if not call_mode_active(state_dir=state_dir):
        return out
    out["active"] = True
    t = str(text or "")
    if _WAKE_RE.search(t):
        out["rule_id"] = "call_overheard/wake_word_passthrough"
        return out
    out["quiet"] = True
    out["rule_id"] = "call_overheard/quiet"
    _reinforce(state_dir)  # r957: the fragment itself keeps the call alive
    try:
        sd = Path(state_dir) if state_dir else _DEFAULT_STATE
        sd.mkdir(parents=True, exist_ok=True)
        with (sd / LEDGER_NAME).open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": time.time(),
                "truth_label": TRUTH_LABEL,
                "rule_id": out["rule_id"],
                "stt_conf": float(stt_conf or 0.0),
                "text_preview": t[:160],
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass
    return out
