#!/usr/bin/env python3
"""
System/swarm_acoustic_sensory_tuning.py — Event 118
══════════════════════════════════════════════════════════════════════════
Acoustic sensory tuning: noisy STT (Whisper) → robust **wake / name** cues.

Doctrine (Architect / Grok lane): treat hot-word hits like **pheromone marks**,
not full language understanding — fuse later with RLHS, VAD, wake engines.

v1 (this file): **fuzzy token + alias** matching + optional multi-cue salience
scalars; append-only receipts when a **fuzzy** wake repairs a regex miss.

Truth label: ``ACOUSTIC_SENSORY_TUNING_EVENT_118``
Ledger: ``.sifta_state/acoustic_tuning.jsonl``
"""
from __future__ import annotations

import difflib
import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from System.jsonl_file_lock import append_line_locked

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
LEDGER = _STATE / "acoustic_tuning.jsonl"

TRUTH_LABEL = "ACOUSTIC_SENSORY_TUNING_EVENT_118"
SCHEMA_VERSION = "acoustic_sensory_tuning.v1"

# Same surface names as RLHS wake regex — supplement only fires when this misses.
_WAKE_CANONICAL = re.compile(r"\b(?:alice|george|architect)\b", re.IGNORECASE)

_TOKEN_RE = re.compile(r"[a-z0-9']+", re.IGNORECASE)

# Common STT mis-hears → canonical handle (lowercase keys).
_PHONETIC_ALIASES: Dict[str, str] = {
    "allis": "alice",
    "ellis": "alice",
    "alex": "alice",
    "allep": "alice",
    "alec": "alice",
    "alis": "alice",
    "alys": "alice",
    "allys": "alice",
    "alla": "alice",
    "ally": "alice",
    "alysia": "alice",
    "jorge": "george",
    "gorge": "george",
    "georg": "george",
    "gorg": "george",
}

# Minimum token length before ratio-based fuzzy is allowed (reduces false CLEAR).
_MIN_FUZZY_LEN = 4
# Ratio must beat this against the canonical spelling for a short token.
_TOKEN_RATIO_MIN = 0.78


def _tokens(text: str) -> List[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or "")]


def _best_ratio(token: str, targets: Tuple[str, ...]) -> Tuple[float, str]:
    best_r = 0.0
    best_t = targets[0]
    for t in targets:
        r = difflib.SequenceMatcher(None, token, t).ratio()
        if r > best_r:
            best_r = r
            best_t = t
    return best_r, best_t


def fuzzy_name_token_hit(transcript: str) -> Tuple[bool, str, float, str]:
    """
    Return (hit, canonical_name, score, detail).

    ``detail`` is ``alias`` | ``ratio`` | ``none``.
    """
    raw = (transcript or "").strip()
    if len(raw) < 2:
        return False, "unknown", 0.0, "none"
    for tok in _tokens(raw):
        if tok in _PHONETIC_ALIASES:
            return True, _PHONETIC_ALIASES[tok], 0.95, "alias"
    best_hit = False
    best_canon = "unknown"
    best_score = 0.0
    best_detail = "none"
    for tok in _tokens(raw):
        if len(tok) < _MIN_FUZZY_LEN:
            continue
        for canon in ("alice", "george", "architect"):
            r, _ = _best_ratio(tok, (canon,))
            if r >= _TOKEN_RATIO_MIN and r > best_score:
                best_score = r
                best_canon = canon
                best_hit = True
                best_detail = "ratio"
    return best_hit, best_canon, round(best_score, 3), best_detail


def is_direct_address_cue(transcript: str) -> bool:
    """Lightweight cues that the human is talking *to* the assistant (not TV)."""
    tl = (transcript or "").lower()
    cues = (
        " you ",
        " your ",
        " hey ",
        " listen ",
        " alice",
        " george ",
        "architect",
        "what do you",
        "can you",
        "could you",
        "would you",
        "tell me",
        " do you think",
    )
    padded = f" {tl} "
    return any(c in padded for c in cues) or tl.strip().startswith("hey ")


def supplement_wake_word(
    text: str,
    *,
    log_fuzzy_hit: bool = True,
    stt_conf: Optional[float] = None,
) -> Tuple[bool, Dict[str, Any]]:
    """
    If canonical regex already finds ``alice|george|architect``, return (False, meta).

    Otherwise, if fuzzy name repair says **wake-class** name (alice/george/architect),
    return (True, meta) so RLHS can treat the turn like ``has_wake_word``.

    When ``log_fuzzy_hit`` and fuzzy fires, append one ledger row.
    """
    raw = (text or "").strip()
    meta: Dict[str, Any] = {"truth_label": TRUTH_LABEL, "via": "none"}
    if _WAKE_CANONICAL.search(raw):
        meta["via"] = "regex_wake_present"
        return False, meta
    hit, canon, score, detail = fuzzy_name_token_hit(raw)
    if not hit or canon not in {"alice", "george", "architect"}:
        meta.update({"via": "no_fuzzy_wake", "fuzzy_canonical": canon, "fuzzy_score": score})
        return False, meta
    if score < _TOKEN_RATIO_MIN and detail == "ratio":
        meta.update({"via": "fuzzy_below_threshold", "fuzzy_canonical": canon, "fuzzy_score": score})
        return False, meta
    # Ratio-only fuzzy matches can false-positive on noise; alias map stays permissive.
    if detail == "ratio" and stt_conf is not None and float(stt_conf) < 0.35:
        meta.update(
            {
                "via": "fuzzy_ratio_low_stt_conf",
                "fuzzy_canonical": canon,
                "fuzzy_score": score,
                "stt_conf": float(stt_conf),
            }
        )
        return False, meta
    meta.update(
        {
            "via": "fuzzy_wake_supplement",
            "fuzzy_canonical": canon,
            "fuzzy_score": score,
            "fuzzy_detail": detail,
        }
    )
    if log_fuzzy_hit:
        _append_fuzzy_receipt(raw, meta)
    return True, meta


def _append_fuzzy_receipt(transcript: str, meta: Dict[str, Any]) -> None:
    row = {
        "schema_version": SCHEMA_VERSION,
        "ts": time.time(),
        "truth_label": TRUTH_LABEL,
        "kind": "fuzzy_wake_hit",
        "transcript_preview": transcript[:200],
        "meta": {k: v for k, v in meta.items() if k != "truth_label"},
    }
    _STATE.mkdir(parents=True, exist_ok=True)
    append_line_locked(
        LEDGER,
        json.dumps(row, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def auditory_salience(
    transcript: str,
    *,
    stt_conf: float = 0.0,
    wake_word_score: float = 0.0,
    mic_energy: float = 0.0,
    gaze_attention: float = 0.0,
) -> Dict[str, Any]:
    """
    Scalar fusion stub for MultiSensing-style gating (all inputs optional).

    v1 keeps weights simple and documented; tune later against receipts.
    """
    hit, canon, score, _detail = fuzzy_name_token_hit(transcript)
    fuzzy_component = score if hit else 0.0
    direct = 1.0 if is_direct_address_cue(transcript) else 0.0
    conf = max(0.0, min(1.0, float(stt_conf or 0.0)))
    wake = max(0.0, min(1.0, float(wake_word_score or 0.0)))
    mic = max(0.0, min(1.0, float(mic_energy or 0.0)))
    gaze = max(0.0, min(1.0, float(gaze_attention or 0.0)))
    salience = min(
        1.0,
        0.34 * conf
        + 0.22 * fuzzy_component
        + 0.18 * direct
        + 0.14 * wake
        + 0.08 * mic
        + 0.04 * gaze,
    )
    return {
        "truth_label": TRUTH_LABEL,
        "auditory_salience": round(salience, 4),
        "stt_confidence": round(conf, 4),
        "fuzzy_name_score": round(fuzzy_component, 4),
        "fuzzy_canonical_guess": canon if hit else "",
        "direct_address": round(direct, 4),
        "wake_word_engine": round(wake, 4),
        "mic_energy": round(mic, 4),
        "gaze_attention": round(gaze, 4),
    }


def transcript_auditory_profile(transcript: str, stt_conf: float = 0.0) -> Dict[str, Any]:
    """Pure summary for conversation / RLHS payloads (no disk I/O)."""
    raw = (transcript or "").strip()
    regex_wake = bool(_WAKE_CANONICAL.search(raw))
    fz_hit, fz_canon, fz_score, fz_detail = fuzzy_name_token_hit(raw)
    sup, sup_meta = supplement_wake_word(raw, log_fuzzy_hit=False, stt_conf=stt_conf)
    return {
        "truth_label": TRUTH_LABEL,
        "regex_wake": regex_wake,
        "fuzzy_wake_supplement_would_apply": bool(sup),
        "fuzzy_canonical": fz_canon if fz_hit else "",
        "fuzzy_score": fz_score,
        "fuzzy_detail": fz_detail,
        "direct_address_cue": bool(is_direct_address_cue(raw)),
        "salience": auditory_salience(raw, stt_conf=stt_conf),
        "supplement_meta": {k: v for k, v in sup_meta.items() if k in ("via", "fuzzy_canonical", "fuzzy_score", "fuzzy_detail")},
    }


def should_promote_to_clear(
    transcript: str,
    *,
    stt_conf: float = 0.0,
    wake_word_score: float = 0.0,
) -> bool:
    """
    Widget-friendly helper: conservative CLEAR hint from acoustic cues alone.

    RLHS remains authoritative; this is for telemetry / future gates.
    """
    raw = (transcript or "").strip()
    if _WAKE_CANONICAL.search(raw):
        return True
    sup, _ = supplement_wake_word(raw, log_fuzzy_hit=False)
    if sup and is_direct_address_cue(raw) and float(stt_conf or 0.0) >= 0.35:
        return True
    if sup and float(wake_word_score or 0.0) >= 0.5:
        return True
    sal = auditory_salience(raw, stt_conf=stt_conf, wake_word_score=wake_word_score)
    return float(sal.get("auditory_salience") or 0.0) >= 0.72


__all__ = [
    "LEDGER",
    "SCHEMA_VERSION",
    "TRUTH_LABEL",
    "auditory_salience",
    "fuzzy_name_token_hit",
    "is_direct_address_cue",
    "should_promote_to_clear",
    "supplement_wake_word",
    "transcript_auditory_profile",
]
