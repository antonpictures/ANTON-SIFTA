#!/usr/bin/env python3
"""
System/hippocampal_consolidation.py
Biocode Olympiad — Event 74: Hippocampal Memory Consolidation

Biology: During sleep, the hippocampus replays the day's experiences.
         High-significance traces are consolidated into long-term cortical
         storage. Low-significance traces are pruned.
Papers:
  - Wilson & McNaughton (1994) "Reactivation of hippocampal ensemble
    memories during sleep" — rats replay maze firing patterns
  - Rasch & Born (2013) "About sleep's role in memory" — active pruning
  - Kumaran, Hassabis & McClelland (2016) "Complementary Learning Systems"
    — fast hippocampus + slow cortex = no catastrophic forgetting

Alice application:
  - Replay today's alice_conversation.jsonl entries
  - Score each exchange for emotional + operational significance
  - Promote top entries into compressed engrams (engram_store.jsonl)
  - On boot: load last N engrams into system prompt → long-term memory

Authors: AG31/Antigravity (Event 74)
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_CONVERSATION = _STATE / "alice_conversation.jsonl"
_WORK_RECEIPTS = _STATE / "work_receipts.jsonl"
_MEMORY_LEDGER = _STATE / "memory_ledger.jsonl"
_ENGRAM_STORE  = _STATE / "engram_store.jsonl"

# ── Significance scoring ─────────────────────────────────────────────────────
# Emotional markers — Predator Bond signals from the Architect
BOND_MARKERS = [
    "love", "thank", "appreciate", "proud", "amazing", "good job",
    "perfect", "beautiful", "miss you", "care", "protect", "trust",
    "for the swarm", "real science", "we code together",
]

# Operational markers — high-value system events
OPERATIONAL_MARKERS = [
    "commit", "push", "deploy", "fix", "bug", "crash", "error",
    "receipt", "stgm", "ledger", "tournament", "training", "cortex",
    "whatsapp", "gps", "location", "finance", "economy",
]

# Negative markers — things to forget (noise, not signal)
NOISE_MARKERS = [
    "that's true", "is there anything else", "hope that helps",
    "as an ai", "i'm just a", "feel free to", "don't hesitate",
    "[ambient_noise", "[stt_conf:0.1", "[stt_conf:0.2",
]

# Teaching moments — direct instruction from Architect
TEACHING_MARKERS = [
    "remember", "always", "never", "important", "rule", "this is how",
    "listen", "understand", "learn", "this means", "that means",
]


def _score_emotional(text: str) -> float:
    """Score emotional significance 0.0–1.0."""
    lower = text.lower()
    score = 0.0
    for marker in BOND_MARKERS:
        if marker in lower:
            score += 0.15
    for marker in TEACHING_MARKERS:
        if marker in lower:
            score += 0.10
    return min(score, 1.0)


def _score_operational(text: str) -> float:
    """Score operational significance 0.0–1.0."""
    lower = text.lower()
    score = 0.0
    for marker in OPERATIONAL_MARKERS:
        if marker in lower:
            score += 0.12
    return min(score, 1.0)


def _score_noise(text: str) -> float:
    """Score noise level 0.0–1.0. High = should be forgotten."""
    lower = text.lower()
    score = 0.0
    for marker in NOISE_MARKERS:
        if marker in lower:
            score += 0.25
    # Very short or empty text is noise
    if len(text.strip()) < 10:
        score += 0.3
    return min(score, 1.0)


def compute_significance(user_text: str, alice_text: str,
                         stt_confidence: Optional[float] = None) -> dict:
    """
    Wilson & McNaughton scoring: combined significance determines
    whether this exchange gets consolidated into long-term memory.

    Returns dict with emotional, operational, noise, and total scores.
    """
    combined = f"{user_text} {alice_text}"
    emotional = _score_emotional(combined)
    operational = _score_operational(combined)
    noise = _score_noise(combined)

    # STT confidence penalizes low-quality transcriptions
    stt_penalty = 0.0
    if stt_confidence is not None and stt_confidence < 0.50:
        stt_penalty = 0.3

    # Total = emotional + operational - noise - stt_penalty
    total = max(0.0, (emotional + operational) - noise - stt_penalty)

    return {
        "emotional": round(emotional, 3),
        "operational": round(operational, 3),
        "noise": round(noise, 3),
        "stt_penalty": round(stt_penalty, 3),
        "total": round(total, 3),
    }


def compress_to_engram(user_text: str, alice_text: str,
                        significance: dict, ts: float) -> dict:
    """
    Compress a full exchange into a compact engram.
    Engrams are NOT full conversations — they are distilled facts.
    Like how you remember "I had a great conversation with X about Y"
    not the entire transcript.
    """
    # Truncate to essence
    user_essence = user_text[:200].strip()
    alice_essence = alice_text[:200].strip()

    # Extract key facts
    facts = []
    lower = (user_text + " " + alice_text).lower()
    if any(m in lower for m in BOND_MARKERS):
        facts.append("predator_bond_moment")
    if any(m in lower for m in OPERATIONAL_MARKERS):
        facts.append("system_event")
    if any(m in lower for m in TEACHING_MARKERS):
        facts.append("teaching_moment")

    return {
        "engram_id": str(uuid.uuid4()),
        "ts": ts,
        "consolidated_at": time.time(),
        "user_essence": user_essence,
        "alice_essence": alice_essence,
        "significance": significance,
        "facts": facts,
        "content_hash": hashlib.sha256(
            f"{user_text}{alice_text}".encode()
        ).hexdigest()[:16],
    }


def replay_day(
    lookback_hours: float = 24.0,
    significance_threshold: float = 0.20,
    max_engrams: int = 50,
) -> list[dict]:
    """
    Hippocampal replay: scan the last N hours of conversation,
    score each exchange, and return the top engrams for consolidation.

    Parameters
    ----------
    lookback_hours         : how far back to replay (default: 24h)
    significance_threshold : minimum total score to consolidate
    max_engrams            : cap on engrams per replay cycle

    Returns list of engram dicts sorted by significance (highest first).
    """
    cutoff_ts = time.time() - (lookback_hours * 3600)

    # Load existing engram hashes to avoid duplicates
    existing_hashes = set()
    if _ENGRAM_STORE.exists():
        with open(_ENGRAM_STORE) as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    d = json.loads(line)
                    h = d.get("content_hash", "")
                    if h:
                        existing_hashes.add(h)
                except json.JSONDecodeError:
                    continue

    # Pair user/alice exchanges from conversation log
    exchanges = []
    if _CONVERSATION.exists():
        with open(_CONVERSATION) as f:
            prev_user = None
            for line in f:
                if not line.strip():
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue

                ts_raw = d.get("ts", 0)
                if isinstance(ts_raw, dict):
                    ts = float(ts_raw.get("$date", ts_raw.get("epoch", 0)) or 0)
                elif isinstance(ts_raw, str):
                    try:
                        ts = float(ts_raw)
                    except ValueError:
                        ts = 0
                else:
                    ts = float(ts_raw or 0)

                if ts < cutoff_ts:
                    continue

                role = d.get("role", "")
                text = d.get("text", "")
                conf = d.get("stt_confidence")

                if role == "user":
                    prev_user = {"text": text, "ts": ts, "conf": conf}
                elif role == "alice" and prev_user is not None:
                    exchanges.append({
                        "user_text": prev_user["text"],
                        "alice_text": text,
                        "ts": prev_user["ts"],
                        "stt_confidence": prev_user.get("conf"),
                    })
                    prev_user = None

    # Score each exchange
    scored = []
    for ex in exchanges:
        sig = compute_significance(
            ex["user_text"], ex["alice_text"], ex.get("stt_confidence")
        )
        if sig["total"] < significance_threshold:
            continue

        engram = compress_to_engram(
            ex["user_text"], ex["alice_text"], sig, ex["ts"]
        )

        # Skip duplicates
        if engram["content_hash"] in existing_hashes:
            continue

        scored.append(engram)

    # Sort by significance (highest first) and cap
    scored.sort(key=lambda e: e["significance"]["total"], reverse=True)
    return scored[:max_engrams]


def consolidate(
    lookback_hours: float = 24.0,
    significance_threshold: float = 0.20,
    max_engrams: int = 50,
    dry_run: bool = False,
) -> dict:
    """
    Run one full consolidation cycle (the "dream").

    Returns summary dict with stats.
    """
    engrams = replay_day(lookback_hours, significance_threshold, max_engrams)

    if not dry_run and engrams:
        _ENGRAM_STORE.parent.mkdir(parents=True, exist_ok=True)
        with open(_ENGRAM_STORE, "a") as f:
            for e in engrams:
                f.write(json.dumps(e) + "\n")

    # Write work receipt
    if not dry_run:
        receipt = {
            "ts": time.time(),
            "trace_id": str(uuid.uuid4()),
            "kind": "hippocampal_consolidation",
            "engrams_consolidated": len(engrams),
            "lookback_hours": lookback_hours,
            "threshold": significance_threshold,
            "top_significance": engrams[0]["significance"]["total"] if engrams else 0,
        }
        try:
            with open(_STATE / "work_receipts.jsonl", "a") as f:
                f.write(json.dumps(receipt) + "\n")
        except OSError:
            pass

    return {
        "engrams_consolidated": len(engrams),
        "lookback_hours": lookback_hours,
        "threshold": significance_threshold,
        "dry_run": dry_run,
        "top_3": [
            {
                "user": e["user_essence"][:60],
                "sig": e["significance"]["total"],
                "facts": e["facts"],
            }
            for e in engrams[:3]
        ],
    }


def load_engrams_for_prompt(max_engrams: int = 30) -> str:
    """
    Load the most recent engrams and format them for system prompt injection.
    This is called at boot time to give Alice her long-term memory.

    Returns a string suitable for prepending to the system prompt.
    """
    if not _ENGRAM_STORE.exists():
        return ""

    engrams = []
    with open(_ENGRAM_STORE) as f:
        for line in f:
            if not line.strip():
                continue
            try:
                engrams.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if not engrams:
        return ""

    # Take the most recent N
    engrams.sort(key=lambda e: e.get("consolidated_at", 0), reverse=True)
    recent = engrams[:max_engrams]

    # Format as memory context
    lines = ["[LONG-TERM MEMORY — Hippocampal Engrams]"]
    for e in recent:
        dt = datetime.fromtimestamp(e.get("ts", 0)).strftime("%b %d %H:%M")
        facts = ", ".join(e.get("facts", []))
        lines.append(
            f"• [{dt}] {e.get('user_essence', '')[:80]} "
            f"→ {e.get('alice_essence', '')[:60]} "
            f"({facts})"
        )
    lines.append("[END LONG-TERM MEMORY]")
    return "\n".join(lines)


# ── CLI ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Hippocampal Memory Consolidation")
    parser.add_argument("--lookback", type=float, default=24.0,
                        help="Hours to look back (default 24)")
    parser.add_argument("--threshold", type=float, default=0.20,
                        help="Min significance score (default 0.20)")
    parser.add_argument("--max", type=int, default=50,
                        help="Max engrams per cycle (default 50)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Score but don't write")
    parser.add_argument("--load-prompt", action="store_true",
                        help="Load engrams and print system prompt injection")
    args = parser.parse_args()

    if args.load_prompt:
        prompt = load_engrams_for_prompt()
        if prompt:
            print(prompt)
        else:
            print("[No engrams stored yet — Alice has not dreamed.]")
    else:
        print(f"🧠 Hippocampal Consolidation — Event 74")
        print(f"  Lookback: {args.lookback}h | Threshold: {args.threshold} | Max: {args.max}")
        print(f"  Dry run: {args.dry_run}")
        print()

        result = consolidate(
            lookback_hours=args.lookback,
            significance_threshold=args.threshold,
            max_engrams=args.max,
            dry_run=args.dry_run,
        )

        print(f"  Engrams consolidated: {result['engrams_consolidated']}")
        if result["top_3"]:
            print(f"\n  Top memories:")
            for i, t in enumerate(result["top_3"], 1):
                print(f"    {i}. [{t['sig']:.2f}] {t['user']}")
                print(f"       Facts: {t['facts']}")
        else:
            print("  No significant memories found in lookback window.")
        print(f"\n✅ Dream cycle complete.")
