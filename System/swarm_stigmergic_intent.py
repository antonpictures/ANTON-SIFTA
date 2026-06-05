#!/usr/bin/env python3
"""swarm_stigmergic_intent.py — command routing that LEARNS, instead of a hardcoded regex. r307.

Architect George 2026-06-01: "do not hardcode — I'm unpredictable — only stigmergy can do it."
He is right: `swarm_edge_intent_router.classify_intent` routes turns with a wall of fixed regex
`phrase_rules` (e.g. `\bsearch\b → search_web`), which is exactly why "search youtube for X"
went to a generic web search. A fixed pattern cannot track an unpredictable owner.

This organ is the stigmergic MEMORY the router consults — not a rival router (§1.A). It does not
replace `classify_intent`; it gives it (and any caller) a learned prior:

  - record_intent(owner_text, lane, target): deposit a pheromone trace of "this phrasing → this
    action, and it was accepted." Successful routings reinforce.
  - correct_intent(owner_text, wrong_target, right_target): the GOLD signal. When George says
    "you opened white watch by mistake, I said victoria secret models runway," that phrasing
    deposits a trace pushing the field AWAY from the wrong target and TOWARD the right one.
  - suggest(owner_text, candidates): score each target by reinforced token-overlap to past
    ACCEPTED traces minus CORRECTED-away ones, with half-life decay (a pheromone). Returns a
    decision only when the field is confident; cold/low-confidence → the caller falls back to
    its own rules. The more George talks and corrects, the better it routes.

§4.2 honesty: this is a derived stigmergic score on the owner's hardware (append-only
.sifta_state/intent_field.jsonl). It is NOT cryptographic and NOT an STGM claim. It is the
field remembering what George meant, so Alice stops needing a brittle pattern for every phrasing.
"""
from __future__ import annotations

import json
import re
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"

TRUTH_LABEL = "ALICE_STIGMERGIC_INTENT_V1"
_LEDGER = "intent_field.jsonl"

DEFAULT_HALF_LIFE_S = 14 * 24 * 3600.0     # a routing memory fades over two weeks unless reused
DECIDE_CONFIDENCE = 0.55                    # below this the field yields to the caller's own rules

# Command stems + stopwords stripped so only CONTENT tokens remain — "please search youtube for X"
# and "yo pull up X on the tube" still share the content of X.
_STOP = {
    "the", "a", "an", "for", "to", "on", "in", "of", "and", "or", "me", "my", "you", "your",
    "please", "pls", "plz", "can", "could", "would", "now", "then", "i", "is", "it", "that",
    "this", "with", "at", "alice", "hey", "ok", "okay", "want", "search", "open", "go", "show",
    "pull", "up", "find", "get", "watch", "let", "lets", "just", "do", "did",
}
_WORD = re.compile(r"[a-z0-9]+")


def _state(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return STATE_DIR
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def tokens(text: str) -> Set[str]:
    return {w for w in _WORD.findall((text or "").lower()) if len(w) >= 2 and w not in _STOP}


def _overlap(a: Set[str], b: Set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / max(1, min(len(a), len(b)))   # overlap coefficient (length-robust)


def _decay(age_s: float, half_life_s: float) -> float:
    return float(0.5 ** (max(0.0, age_s) / half_life_s)) if half_life_s > 0 else 0.0


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


def record_intent(owner_text: str, lane: str, target: str, *, query: str = "",
                  outcome: str = "accepted", state_dir: Optional[Path | str] = None,
                  now: Optional[float] = None) -> Dict[str, Any]:
    """Deposit a pheromone trace: this phrasing routed to (lane,target) and was accepted."""
    row = {
        "ts": float(time.time() if now is None else now),
        "kind": "INTENT", "truth_label": TRUTH_LABEL,
        "owner_text": str(owner_text)[:240], "owner_tokens": sorted(tokens(owner_text)),
        "lane": str(lane), "target": str(target), "outcome": str(outcome),
        "query": str(query)[:160],
    }
    _append(row, state_dir)
    return row


def correct_intent(owner_text: str, *, wrong_target: str, right_target: str,
                   right_lane: str = "", state_dir: Optional[Path | str] = None,
                   now: Optional[float] = None) -> Dict[str, Any]:
    """The owner correction signal: this phrasing meant right_target, NOT wrong_target."""
    row = {
        "ts": float(time.time() if now is None else now),
        "kind": "INTENT_CORRECTION", "truth_label": TRUTH_LABEL,
        "owner_text": str(owner_text)[:240], "owner_tokens": sorted(tokens(owner_text)),
        "wrong_target": str(wrong_target), "right_target": str(right_target),
        "right_lane": str(right_lane),
    }
    _append(row, state_dir)
    return row


def suggest(owner_text: str, candidates: Optional[List[str]] = None, *,
            state_dir: Optional[Path | str] = None, now: Optional[float] = None,
            half_life_s: float = DEFAULT_HALF_LIFE_S) -> Dict[str, Any]:
    """Stigmergic routing prior. Score each target by reinforced token-overlap to past accepted
    traces minus corrected-away ones, with decay. Returns decided=True only when confident."""
    t = float(time.time() if now is None else now)
    q = tokens(owner_text)
    scores: Dict[str, float] = defaultdict(float)
    lanes: Dict[str, str] = {}
    support: Dict[str, int] = defaultdict(int)
    if q:
        for r in _rows(state_dir):
            sim = _overlap(q, set(r.get("owner_tokens") or []))
            if sim <= 0:
                continue
            w = sim * _decay(t - float(r.get("ts", 0) or 0), half_life_s)
            if w <= 0:
                continue
            if r.get("kind") == "INTENT" and r.get("outcome") == "accepted":
                tgt = str(r.get("target") or "")
                if tgt:
                    scores[tgt] += w
                    lanes[tgt] = str(r.get("lane") or lanes.get(tgt, ""))
                    support[tgt] += 1
            elif r.get("kind") == "INTENT_CORRECTION":
                rt = str(r.get("right_target") or "")
                wt = str(r.get("wrong_target") or "")
                if rt:
                    scores[rt] += w
                    lanes[rt] = str(r.get("right_lane") or lanes.get(rt, ""))
                    support[rt] += 1
                if wt:
                    scores[wt] -= w
    pool = {k: v for k, v in scores.items() if (candidates is None or k in candidates)}
    if not pool:
        return {"decided": False, "best_target": "", "target": "", "lane": "",
                "confidence": 0.0, "field_size": len(_rows(state_dir)), "scores": {}}
    best = max(pool, key=lambda k: pool[k])
    best_score = pool[best]
    total = sum(abs(v) for v in pool.values()) or 1.0
    confidence = max(0.0, best_score) / total
    decided = bool(best_score > 0 and confidence >= DECIDE_CONFIDENCE and support[best] >= 1)
    return {
        "decided": decided,
        "best_target": best,                      # the raw argmax (what the field learned)
        "target": best if decided else "",        # gated: only when confident enough to act
        "lane": lanes.get(best, ""),
        "confidence": round(confidence, 3), "support": support.get(best, 0),
        "field_size": sum(support.values()), "scores": {k: round(v, 4) for k, v in pool.items()},
        "truth_label": TRUTH_LABEL,
    }


__all__ = ["TRUTH_LABEL", "tokens", "record_intent", "correct_intent", "suggest", "DECIDE_CONFIDENCE"]
