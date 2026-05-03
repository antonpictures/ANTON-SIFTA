#!/usr/bin/env python3
"""WISH_003 -- Alice Wake Ear.

Fuzzy wake-word and noisy STT recovery for the shared room.

The job is narrow: when YouTube/movie audio is present, recover direct turns
where the owner is trying to wake or address Alice but Whisper mangles the name
("Alice" -> "Alep", "all is", etc.). This is a receipt-backed reflex, not a
conversation script. It never stores raw audio, and far-field replay evidence
keeps media dialogue from becoming a direct prompt.
"""
from __future__ import annotations

import json
import math
import re
import time
import uuid
from pathlib import Path
from typing import Any, Mapping, Optional

from System.jsonl_file_lock import append_line_locked

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
LEDGER = STATE_DIR / "alice_wake_ear.jsonl"

TRUTH_LABEL = "ALICE_WAKE_EAR_WISH_003"
DIRECT_THRESHOLD = 0.66
MIN_NAME_SIMILARITY = 0.72

_TARGET_NAMES = ("alice", "george")
_WAKE_PREFIXES = {
    "alice": ("ali", "aly", "ale", "all", "ell", "el"),
    "george": ("geo", "geor", "jor", "jorj"),
}
_OWNER_DIRECT_RE = re.compile(
    r"\b(?:"
    r"can\s+you|could\s+you|do\s+you|are\s+you|will\s+you|"
    r"hear\s+me|listen\s+to\s+me|talk\s+to\s+me|answer\s+me|"
    r"who\s+am\s+i|what(?:'s| is)\s+my\s+name|"
    r"i\s+(?:am|['’]m|was|want|need|asked|said|mean|feel|think)|"
    r"my\s+(?:voice|question|name|body)|"
    r"you\s+and\s+me|we\s+(?:are|were|need|should|watch|watched)"
    r")\b",
    re.IGNORECASE,
)
_NARRATION_RE = re.compile(
    r"\b(?:"
    r"therefore|however|universe|multiverse|theory|researchers?|"
    r"according\s+to|the\s+video|the\s+speaker|in\s+this\s+episode|"
    r"chapter|documentary|experiment|civilization"
    r")\b",
    re.IGNORECASE,
)


def _tokenize(text: str) -> list[str]:
    return [m.group(0).casefold() for m in re.finditer(r"[a-zA-Z][a-zA-Z']{1,18}", text or "")]


def _candidate_tokens(tokens: list[str]) -> list[str]:
    out: list[str] = []
    for i, token in enumerate(tokens):
        out.append(re.sub(r"[^a-z]", "", token))
        if i + 1 < len(tokens):
            out.append(re.sub(r"[^a-z]", "", token + tokens[i + 1]))
    return [x for x in out if x]


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(
                min(
                    prev[j] + 1,
                    cur[j - 1] + 1,
                    prev[j - 1] + (0 if ca == cb else 1),
                )
            )
        prev = cur
    return prev[-1]


def _edit_similarity(a: str, b: str) -> float:
    denom = max(len(a), len(b), 1)
    return max(0.0, 1.0 - (_levenshtein(a, b) / denom))


def _prefix_similarity(candidate: str, target: str) -> float:
    prefixes = _WAKE_PREFIXES.get(target, ())
    if len(candidate) < 4 or len(candidate) > 8:
        return 0.0
    for prefix in prefixes:
        if candidate.startswith(prefix):
            # Prefix evidence is not certainty. It just rescues common STT
            # phonetic collapses such as "all is" -> Alice.
            return 0.74 + min(0.10, 0.02 * max(0, len(candidate) - len(prefix)))
    return 0.0


def best_wake_name_match(text: str) -> dict[str, Any]:
    tokens = _tokenize(text)
    best = {
        "target": "",
        "candidate": "",
        "similarity": 0.0,
    }
    for candidate in _candidate_tokens(tokens):
        for target in _TARGET_NAMES:
            score = max(
                _edit_similarity(candidate, target),
                _prefix_similarity(candidate, target),
            )
            if score > float(best["similarity"]):
                best = {
                    "target": target,
                    "candidate": candidate,
                    "similarity": round(score, 3),
                }
    return best


def _float01(value: Any, default: float = 0.0) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except Exception:
        return default


def _sanitize_acoustic(acoustic_fingerprint: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(acoustic_fingerprint, Mapping):
        return {}
    allowed = (
        "truth_label",
        "formula_revision",
        "channel_cue",
        "nearfield_voice_likelihood",
        "farfield_replay_likelihood",
        "crest_factor",
        "spectral_flatness",
        "mfcc_coeff_std",
        "hnr_proxy",
        "am_depth",
    )
    out: dict[str, Any] = {}
    for key in allowed:
        value = acoustic_fingerprint.get(key)
        if isinstance(value, (int, float, str, bool)) or value is None:
            out[key] = value
    return out


def _sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def classify_wake_turn(
    text: str,
    *,
    stt_conf: float = 0.0,
    acoustic_fingerprint: Mapping[str, Any] | None = None,
    focus_context: str = "",
) -> dict[str, Any]:
    """Return a direct/ambient wake-ear decision.

    This function is intentionally deterministic and side-effect free. Use
    `write_wake_receipt` when a caller wants append-only proof.
    """
    clean = " ".join(str(text or "").split())
    if not clean:
        return {
            "truth_label": TRUTH_LABEL,
            "route": "ambient",
            "reason": "empty_text",
            "confidence": 1.0,
            "wake_score": 0.0,
            "name_match": {"target": "", "candidate": "", "similarity": 0.0},
        }

    fp = _sanitize_acoustic(acoustic_fingerprint)
    near = _float01(fp.get("nearfield_voice_likelihood", 0.0))
    far = _float01(fp.get("farfield_replay_likelihood", 0.0))
    cue = str(fp.get("channel_cue") or "")
    conf = _float01(stt_conf)
    words = len(_tokenize(clean))
    name_match = best_wake_name_match(clean)
    name_sim = float(name_match.get("similarity") or 0.0)
    has_direct_shape = bool(_OWNER_DIRECT_RE.search(clean))
    has_narration_shape = bool(_NARRATION_RE.search(clean))
    has_media_context = bool(re.search(r"\b(?:youtube|movie|media|video|tv|caption)\b", focus_context or "", re.I))

    logit = -2.25
    logit += (conf - 0.42) * 1.15
    logit += name_sim * 3.55
    logit += near * 1.55
    logit -= far * 2.45
    if cue == "nearfield_voice_likely":
        logit += 0.65
    elif cue == "farfield_replay_likely":
        logit -= 0.85
    if has_direct_shape:
        logit += 1.15
    if words <= 16:
        logit += 0.35
    if has_media_context:
        logit -= 0.15
    if has_narration_shape:
        logit -= 0.90
    if words >= 24:
        logit -= 0.85

    score = round(_sigmoid(logit), 3)
    direct = (
        name_sim >= MIN_NAME_SIMILARITY
        and score >= DIRECT_THRESHOLD
        and far < 0.78
    )
    if direct:
        if near >= 0.60 or cue == "nearfield_voice_likely":
            reason = "fuzzy_wake_name_nearfield"
        elif has_direct_shape:
            reason = "fuzzy_wake_name_direct_shape"
        else:
            reason = "fuzzy_wake_name"
        route = "direct"
        confidence = score
    else:
        route = "ambient"
        if far >= 0.78 or cue == "farfield_replay_likely":
            reason = "farfield_replay_suppressed"
        elif name_sim < MIN_NAME_SIMILARITY:
            reason = "no_wake_name_evidence"
        else:
            reason = "wake_score_below_threshold"
        confidence = round(1.0 - score, 3)

    return {
        "truth_label": TRUTH_LABEL,
        "route": route,
        "reason": reason,
        "confidence": confidence,
        "wake_score": score,
        "name_match": name_match,
        "features": {
            "stt_confidence": conf,
            "nearfield_voice_likelihood": near,
            "farfield_replay_likelihood": far,
            "channel_cue": cue,
            "word_count": words,
            "direct_shape": has_direct_shape,
            "narration_shape": has_narration_shape,
            "media_context": has_media_context,
        },
    }


def write_wake_receipt(
    decision: Mapping[str, Any],
    *,
    text: str,
    stt_conf: float = 0.0,
    focus_context: str = "",
    acoustic_fingerprint: Mapping[str, Any] | None = None,
    root: Optional[Path] = None,
) -> dict[str, Any]:
    path = (Path(root) / ".sifta_state" / "alice_wake_ear.jsonl") if root else LEDGER
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": time.time(),
        "trace_id": str(uuid.uuid4()),
        "truth_label": TRUTH_LABEL,
        "writer": "swarm_alice_wake_ear",
        "route": str(decision.get("route") or "ambient"),
        "reason": str(decision.get("reason") or ""),
        "confidence": _float01(decision.get("confidence", 0.0)),
        "wake_score": _float01(decision.get("wake_score", 0.0)),
        "name_match": decision.get("name_match") if isinstance(decision.get("name_match"), Mapping) else {},
        "features": decision.get("features") if isinstance(decision.get("features"), Mapping) else {},
        "stt_confidence": _float01(stt_conf),
        "text_preview": str(text or "")[:220],
        "focus_preview": str(focus_context or "")[:500],
        "acoustic_fingerprint": _sanitize_acoustic(acoustic_fingerprint),
        "truth_note": (
            "WISH_003 wake-ear scored fuzzy direct address before media routing. "
            "Raw audio is not stored."
        ),
    }
    append_line_locked(path, json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return row


__all__ = [
    "TRUTH_LABEL",
    "best_wake_name_match",
    "classify_wake_turn",
    "write_wake_receipt",
]
