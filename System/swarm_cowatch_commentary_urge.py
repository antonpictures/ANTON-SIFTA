#!/usr/bin/env python3
"""swarm_cowatch_commentary_urge.py — WHEN Alice speaks over a video is a pheromone, not a timer. r323.

Architect George 2026-06-01: "that extra trigger has to be a stigmergic variable. I'm the OS user,
I'm the data, my behaviour for it."

He is right, and a fixed cadence ("comment every 30s") is exactly the narrow human-designed bound
§0 says to exceed. So the urge to comment during co-watch is a PHEROMONE built from George's own
behaviour:

  - His behaviour DEPOSITS stimulus: he pauses (he is attending), he speaks, the scene/segment
    changes, a salient title/channel moment lands. Each raises the urge.
  - When she comments, that lays a REFRACTORY trace that decays fast (minutes) — so she does not
    spam; the urge has to rebuild before she speaks again.
  - His RESPONSE teaches the field: if he engages with a comment (replies, "great job", keeps the
    thread), that context gets a REWARD deposit and the bar to speak there drops. If he ignores it,
    says "quiet / stop", or she talked over other sound, that context gets an AVERSION deposit and
    the bar rises. George, unpredictable, shapes when she speaks — the cadence EMERGES.

This reuses the r307 `swarm_stigmergic_intent` mechanics (content tokens + half-life decay +
overlap-weighted deposits) on a NEW axis — timing/desire, not routing — so it is a sibling field,
not a rival organ (§1.A). Pure stdlib, no Qt, append-only `.sifta_state/cowatch_urge_field.jsonl`,
headless-testable. §4.2 honesty: a derived stigmergic score on the owner's hardware — NOT
cryptographic, NOT an STGM claim. It is the field remembering how George likes to co-watch.
"""
from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

try:
    # Reuse the r307 content-token extractor so routing and urge share one notion of "what was said".
    from System.swarm_stigmergic_intent import tokens as _intent_tokens
except Exception:  # pragma: no cover - fallback keeps the organ standalone
    import re as _re
    _WORD = _re.compile(r"[a-z0-9]+")
    _STOP = {"the", "a", "an", "for", "to", "on", "in", "of", "and", "or", "it", "is"}

    def _intent_tokens(text: str) -> Set[str]:
        return {w for w in _WORD.findall((text or "").lower()) if len(w) >= 2 and w not in _STOP}

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
TRUTH_LABEL = "ALICE_COWATCH_URGE_V1"
_LEDGER = "cowatch_urge_field.jsonl"

# Two pheromones, two memories:
#   stimulus / reward / aversion fade over the session-to-days range (George's taste persists),
#   the refractory after a comment fades in MINUTES (so she pauses between comments, not forever).
STIMULUS_HALF_LIFE_S = 60 * 60.0          # an hour
PREFERENCE_HALF_LIFE_S = 7 * 24 * 3600.0  # a week — how George likes co-watch is long memory
REFRACTORY_HALF_LIFE_S = 120.0            # two minutes — the gap between comments rebuilds

# Cold-start bar. This is only the seed comparator; George's reward/aversion deposits move the
# EFFECTIVE bar (reward lowers it, aversion raises it), so the firing cadence is learned, not fixed.
BASE_THRESHOLD = 1.0
# A fresh comment deposits this much refractory; while it has not decayed, the urge is held down.
COMMENT_REFRACTORY_WEIGHT = 4.5

# Default deposit weights for owner behaviours (relative emphasis, all reshaped by the field).
SIGNAL_WEIGHTS = {
    "owner_paused": 1.1,      # he paused — he is attending, a good moment to speak
    "owner_spoke": 0.9,       # he is interacting
    "owner_reaction": 1.0,    # he reacted to the screen ("wow", laugh, "look at that")
    "scene_change": 0.7,      # the video moved to a new segment
    "salient_moment": 0.8,    # a salient title/channel/visual beat
    "dwell": 0.4,             # time simply passing on the same video (gentle build)
}


def _state(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return STATE_DIR
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def _decay(age_s: float, half_life_s: float) -> float:
    return float(0.5 ** (max(0.0, age_s) / half_life_s)) if half_life_s > 0 else 0.0


def _overlap(a: Set[str], b: Set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / max(1, min(len(a), len(b)))


def context_tokens(*parts: str) -> Set[str]:
    """Content tokens for a co-watch context — video title, channel, owner words, day segment."""
    out: Set[str] = set()
    for p in parts:
        out |= _intent_tokens(p or "")
    return out


def _append(row: Dict[str, Any], state_dir: Optional[Path | str]) -> None:
    try:
        path = _state(state_dir) / _LEDGER
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _rows(state_dir: Optional[Path | str]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    try:
        with (_state(state_dir) / _LEDGER).open("r", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    try:
                        out.append(json.loads(line))
                    except Exception:
                        continue
    except Exception:
        return []
    return out


def deposit_owner_signal(kind: str, context: str = "", *, weight: Optional[float] = None,
                         note: str = "", state_dir: Optional[Path | str] = None,
                         now: Optional[float] = None) -> Dict[str, Any]:
    """George's behaviour raises the urge. `kind` is one of SIGNAL_WEIGHTS (or any label).
    `context` is the co-watch context (video title/channel + his words) so the urge is per-context."""
    w = float(SIGNAL_WEIGHTS.get(kind, 0.6) if weight is None else weight)
    row = {
        "ts": float(time.time() if now is None else now),
        "kind": "STIMULUS", "signal": str(kind), "weight": w,
        "ctx": sorted(context_tokens(context)), "note": str(note)[:160],
        "truth_label": TRUTH_LABEL,
    }
    _append(row, state_dir)
    return row


def note_comment_made(context: str = "", *, state_dir: Optional[Path | str] = None,
                      now: Optional[float] = None) -> Dict[str, Any]:
    """She just commented — lay a fast-decaying refractory trace so she does not spam."""
    row = {
        "ts": float(time.time() if now is None else now),
        "kind": "COMMENT", "weight": COMMENT_REFRACTORY_WEIGHT,
        "ctx": sorted(context_tokens(context)), "truth_label": TRUTH_LABEL,
    }
    _append(row, state_dir)
    return row


def reinforce(context: str, *, engaged: bool, signal: str = "",
              state_dir: Optional[Path | str] = None, now: Optional[float] = None) -> Dict[str, Any]:
    """George's response teaches the field. engaged=True (he replied / 'great job' / kept talking)
    deposits REWARD — the bar to comment in similar contexts drops. engaged=False (ignored / 'quiet'
    / talked-over) deposits AVERSION — the bar rises. This is how his behaviour tunes the cadence."""
    row = {
        "ts": float(time.time() if now is None else now),
        "kind": "REWARD" if engaged else "AVERSION", "weight": 1.0,
        "ctx": sorted(context_tokens(context)), "signal": str(signal)[:120],
        "truth_label": TRUTH_LABEL,
    }
    _append(row, state_dir)
    return row


def comment_pressure(context: str = "", *, state_dir: Optional[Path | str] = None,
                     now: Optional[float] = None) -> Dict[str, Any]:
    """The live urge for THIS context. pressure = decayed stimulus + learned reward-bias
    - decayed refractory. Each term is overlap-weighted to the context so George's taste is
    per-video, not global."""
    t = float(time.time() if now is None else now)
    ctx = context_tokens(context)
    stimulus = 0.0
    refractory = 0.0
    reward = 0.0
    aversion = 0.0
    for r in _rows(state_dir):
        age = t - float(r.get("ts", 0) or 0)
        if age < 0:
            continue
        kind = r.get("kind")
        w = float(r.get("weight", 0) or 0)
        row_ctx = set(r.get("ctx") or [])
        # Untagged rows (no ctx) apply globally; tagged rows weight by overlap to this context.
        sim = 1.0 if not row_ctx or not ctx else max(_overlap(ctx, row_ctx), 0.15)
        if kind == "STIMULUS":
            stimulus += w * sim * _decay(age, STIMULUS_HALF_LIFE_S)
        elif kind == "COMMENT":
            refractory += w * sim * _decay(age, REFRACTORY_HALF_LIFE_S)
        elif kind == "REWARD":
            reward += w * sim * _decay(age, PREFERENCE_HALF_LIFE_S)
        elif kind == "AVERSION":
            aversion += w * sim * _decay(age, PREFERENCE_HALF_LIFE_S)
    reward_bias = reward - aversion
    pressure = stimulus + reward_bias - refractory
    return {
        "pressure": round(pressure, 4),
        "stimulus": round(stimulus, 4),
        "reward_bias": round(reward_bias, 4),
        "refractory": round(refractory, 4),
        "truth_label": TRUTH_LABEL,
    }


def should_comment(context: str = "", *, base_threshold: float = BASE_THRESHOLD,
                   state_dir: Optional[Path | str] = None, now: Optional[float] = None) -> Dict[str, Any]:
    """Stigmergic decision: does the urge cross the bar right now? No clock, no fixed interval.
    The bar is BASE_THRESHOLD already folded with the field (reward_bias is inside pressure), and a
    fresh comment's refractory holds her quiet until it decays. Cold field → low pressure → silence,
    which is the right default (George said silence is fine)."""
    p = comment_pressure(context, state_dir=state_dir, now=now)
    fires = bool(p["pressure"] >= float(base_threshold))
    if fires:
        reason = "urge_crossed_bar"
    elif p["refractory"] > 0.5:
        reason = "refractory_recent_comment"
    elif p["reward_bias"] < 0:
        reason = "owner_aversion_holding_quiet"
    else:
        reason = "urge_below_bar"
    out = {"comment": fires, "reason": reason, "threshold": float(base_threshold)}
    out.update(p)
    return out


__all__ = [
    "TRUTH_LABEL", "SIGNAL_WEIGHTS", "BASE_THRESHOLD",
    "context_tokens", "deposit_owner_signal", "note_comment_made", "reinforce",
    "comment_pressure", "should_comment",
]
