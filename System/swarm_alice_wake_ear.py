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

# Architect 2026-05-13 02:10 — these were hardcoded "alice" / "george"
# literals, which broke when the owner renamed her in Layer 1 (any node
# where she is "Sophia", "Lola", etc. would have a dead wake-ear). They
# now seed only the *phonetic prefix table* for known stems. The active
# wake targets are computed dynamically from the kernel cascade via
# `_active_target_names()`.
_PHONETIC_PREFIXES = {
    "alice":  ("ali", "aly", "ale", "all", "ell", "el"),
    "george": ("geo", "geor", "jor", "jorj"),
    "sophia": ("sof", "soph", "sofi"),
    "lola":   ("lol", "lo"),
    "jeff":   ("jef", "jeff"),
    "daniel": ("dan", "dani", "danl"),
}


def _active_target_names() -> tuple[str, ...]:
    """Live wake targets read from Layer 1 cascade — `ai_can_be_called()`
    plus owner's first-name vocative. Falls back to ('alice','george')
    only if the cascade can't be imported (e.g. very early boot)."""
    try:
        from System.swarm_kernel_identity import (
            ai_can_be_called, owner_vocative_for_talk
        )
        names: list[str] = []
        for n in (ai_can_be_called() or []):
            s = str(n or "").strip().lower()
            if s and s not in names:
                names.append(s)
        try:
            voc = (owner_vocative_for_talk() or "").strip().lower()
        except Exception:
            voc = ""
        if voc:
            # Owner often has multiple given names ("Ioan George Anton")
            # — accept ALL tokens of length >= 3 as wake targets so any
            # of them spoken alone wakes her. Skip very short stop-words.
            for tok in voc.split():
                tok = tok.strip().lower()
                if len(tok) >= 3 and tok not in names:
                    names.append(tok)
        if not names:
            return ("alice", "george")
        return tuple(names)
    except Exception:
        return ("alice", "george")


def _prefixes_for_target(target: str) -> tuple[str, ...]:
    """Prefix list for a target. Known stems get their phonetic-collapse
    rescues; unknown stems get the first three letters as a weak fallback."""
    t = target.lower()
    if t in _PHONETIC_PREFIXES:
        return _PHONETIC_PREFIXES[t]
    return (t[:3],) if len(t) >= 3 else ()
# ── Architect 2026-05-13 05:20 — Media-context awareness ─────────────────
# When the OS user has a media-producing app frontmost (Safari/Chrome with
# YouTube open, QuickTime, Spotify, etc.), nearfield audio is most likely
# the *content* of that app, NOT direct speech. The wake-ear already
# accepted focus_context but only downweighted it by -0.15; that was too
# weak. We now (1) classify the active app explicitly via this set, and
# (2) apply a much stronger -1.50 logit penalty so media audio stops
# waking Alice unless her Layer-1 name is unambiguously present.
_KNOWN_MEDIA_APPS = frozenset({
    # Browsers — usually a tab is showing a video/audio context
    "safari", "chrome", "google chrome", "firefox", "brave", "arc",
    "edge", "microsoft edge", "opera", "vivaldi", "tor browser",
    # macOS native media apps
    "quicktime player", "quicktime", "music", "tv", "podcasts", "books",
    "photos",
    # Third-party media apps
    "spotify", "vlc", "iina", "mpv", "plex", "kodi", "netflix",
    "youtube", "youtube music", "soundcloud", "audible",
    # Communication apps that play remote audio
    "zoom", "facetime", "teams", "microsoft teams", "google meet",
    "webex", "skype", "discord", "slack",
})


def _active_app_is_media() -> tuple[bool, str]:
    """Return (is_media, app_name_lowercase). Reads the most recent
    app_focus.jsonl row, freshness-gated to 120 s."""
    try:
        path = STATE_DIR / "app_focus.jsonl"
        if not path.exists():
            return (False, "")
        with path.open("rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - 8192))
            tail = fh.read().decode("utf-8", errors="ignore")
        last_app = ""
        last_ts = 0.0
        for line in reversed(tail.splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            last_app = str(r.get("app") or "").strip()
            last_ts = float(r.get("ts") or 0)
            if last_app:
                break
        if not last_app or last_ts <= 0:
            return (False, "")
        if (time.time() - last_ts) > 120.0:
            return (False, "")
        low = last_app.lower()
        return (low in _KNOWN_MEDIA_APPS, low)
    except Exception:
        return (False, "")


_OWNER_DIRECT_RE = re.compile(
    r"\b(?:"
    r"can\s+you|could\s+you|do\s+you|are\s+you|will\s+you|did\s+you|"
    r"have\s+you|would\s+you|should\s+you|hear\s+me|listen\s+to\s+me|"
    r"talk\s+to\s+me|answer\s+me|tell\s+me|show\s+me|help\s+me|"
    r"who\s+am\s+i|what(?:'s| is)\s+my\s+name|"
    # Architect 2026-05-14 06:40 — expanded verb list. The investor-demo
    # transcript caught "I have paused", "I just told", "I paused" — all
    # missed by the prior regex which only covered "i am/was/want/need/...".
    r"i\s+(?:am|['’]m|was|want|need|asked|said|mean|feel|think|"
    r"have|told|paused|did|saw|heard|see|hear|read|gave|just|"
    r"would|will|wanted|needed|noticed|expected)|"
    r"my\s+(?:voice|question|name|body|video|tab|screen|computer)|"
    r"you\s+and\s+me|we\s+(?:are|were|need|should|watch|watched)|"
    # Direct verb-first imperatives addressed to her
    r"(?:please\s+)?(?:pause|play|stop|start|open|close|change|"
    r"check|read|show|tell|hear|listen|look|focus|wake|sleep|run|"
    r"answer|respond|reply)\s+(?:the|my|this|that|it|now|with)"
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
    prefixes = _prefixes_for_target(target)
    if len(candidate) < 4 or len(candidate) > 8:
        return 0.0
    if target == "alice" and candidate.startswith("all") and not candidate.startswith(
        ("alli", "ally", "alis", "alys", "ales", "alle", "alice")
    ):
        # "all is" is a real STT collapse for "Alice"; "all and" from
        # normal narration ("kill us all and...") is not a wake word.
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
        for target in _active_target_names():
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

    # ── Layer 1 fast-path ─────────────────────────────────────────
    # Architect 2026-05-14 06:40: "THE OPERATING SYSTEM NEEDS TO RESPOND
    # BETTER TO HER NAME REGISTERED IN LAYER 1". Hearing the name at the
    # start of an utterance is attention — it must wake DIRECT instantly,
    # bypassing logit / media-context / score-threshold. Required:
    #   - the first token must match a known wake target (alice / george /
    #     owner vocative) with similarity ≥ 0.85 (high bar — no fuzzy mishears)
    #   - the utterance must not be JUST the name alone (those reach the
    #     normal path so the "Alice." → "What is on your mind?" handshake
    #     still works)
    # This is Layer 1 attention, NOT authorization. The cortex still
    # decides what to do with the turn; the fast-path only guarantees
    # direct routing so the cortex SEES it.
    _name_match_early = best_wake_name_match(clean)
    _name_sim_early = float(_name_match_early.get("similarity") or 0.0)
    _first_token = (_tokenize(clean)[:1] or [""])[0]
    _first_token_sim = 0.0
    if _first_token:
        for _target in _active_target_names():
            _s = max(_edit_similarity(_first_token, _target),
                     _prefix_similarity(_first_token, _target))
            if _s > _first_token_sim:
                _first_token_sim = _s
    _word_count_early = len(_tokenize(clean))
    if _first_token_sim >= 0.85 and _word_count_early >= 2:
        # Hearing the name first → instant attention. Skip the logit math.
        return {
            "truth_label": TRUTH_LABEL,
            "route": "direct",
            "reason": "layer1_name_at_utterance_start",
            "confidence": 0.98,
            "wake_score": 0.98,
            "name_match": dict(_name_match_early),
            "first_token": _first_token,
            "first_token_similarity": round(_first_token_sim, 3),
        }
    # ──────────────────────────────────────────────────────────────

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
    has_media_context = bool(re.search(r"\b(?:youtube|movie|media|video|tv|caption|episode|podcast|stream|watching|listening)\b", focus_context or "", re.I))
    # Layer 1+ stigmergic awareness: query the live app_focus ledger.
    _active_media, _active_app_name = _active_app_is_media()
    if _active_media:
        has_media_context = True

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
        # Architect 2026-05-13 05:25: media penalty scales with how
        # ambiguous the name match is. Strong direct address (e.g.
        # "Alice, what time is it?") still wakes — only ambient
        # narration with no clear name is silenced.
        if name_sim >= 0.85:
            # Clear name match in the transcript — only a tiny bias.
            logit -= 0.10
        elif name_sim >= MIN_NAME_SIMILARITY:  # fuzzy name match
            logit -= 0.50
        else:
            # No name match at all — full penalty.
            logit -= 1.50
        # If the active app is a *known* media producer (not just a tab
        # keyword) AND there's no plausible name match, hard-route
        # ambient — short-circuit so we don't waste the cortex on a
        # likely YouTube clip / podcast / Zoom audio.
        if _active_media and name_sim < MIN_NAME_SIMILARITY:
            return {
                "truth_label": TRUTH_LABEL,
                "route": "ambient",
                "reason": f"active_media_app:{_active_app_name}",
                "confidence": 0.95,
                "wake_score": 0.0,
                "name_match": dict(name_match),
                "media_context": True,
                "active_media_app": _active_app_name,
            }
    if has_narration_shape:
        logit -= 0.90
    if words >= 24:
        logit -= 0.85

    # ── CO-WATCH AMBIENT BIAS (AG46 2026-05-07) ───────────────────────────
    # When a YouTube/documentary co-watch segment is active AND the turn is
    # long (≥20 words) AND there is no direct Alice-address name match,
    # apply a heavy ambient bias. Long, coherent narration at medium-high STT
    # confidence is exactly what documentary audio looks like — don't let it
    # bypass the media gate just because Whisper transcribed it cleanly.
    #
    # We only apply this when name_sim is LOW (no wake-word evidence).
    # If George addresses Alice in 20+ words, name_sim will be high enough to
    # overcome this bias; the bias only catches ambient narration.
    try:
        from System.swarm_architect_day_segments import get_active_cowatch_segment
        _cw_seg = get_active_cowatch_segment()
        if _cw_seg and name_sim < MIN_NAME_SIMILARITY:
            if words >= 20:
                logit -= 1.80   # strong ambient push for long narration during co-watch
            elif words >= 12:
                logit -= 0.90   # medium push for medium-length turns during co-watch
    except Exception:
        pass
    # ────────────────────────────────────────────────────────────────────────


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
