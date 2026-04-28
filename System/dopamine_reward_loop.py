#!/usr/bin/env python3
"""
System/dopamine_reward_loop.py
Biocode Olympiad — Event 75: Dopaminergic Reward Signal

Biology: Dopamine neurons fire when reward exceeds prediction (positive
         prediction error). They suppress when reward is less than expected
         (negative prediction error). Over time, the organism learns which
         action patterns lead to reward and which lead to punishment.

Papers:
  - Schultz, Dayan & Montague (1997) "A neural substrate of prediction
    and reward" — dopamine = temporal difference error δ = r - V(s)
  - Sutton & Barto (2018) "Reinforcement Learning: An Introduction"
    — TD learning is universal in biological and artificial agents
  - Silver et al. (2021) "Reward is enough" — all intelligence can be
    formulated as reward maximization

Alice application:
  - The Architect's explicit reactions ARE the reward signal
  - "good job" / "perfect" / "amazing" → positive δ → reinforce action
  - "no" / "wrong" / "stop" → negative δ → suppress action
  - Track accumulated reward per action category
  - Adapt Basal Ganglia temperature based on reward history
  - Feed reward summary into system prompt so Alice knows what works

Authors: AG31/Antigravity (Event 75)
"""
from __future__ import annotations

import json
import math
import re
import time
import uuid
from pathlib import Path
from typing import Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_REWARD_LEDGER = _STATE / "dopamine_reward_ledger.jsonl"
_CONVERSATION = _STATE / "alice_conversation.jsonl"

# ── Reward signals ────────────────────────────────────────────────────────────
# Positive δ: Architect is pleased → reinforce last action pattern
POSITIVE_MARKERS = {
    # Strong positive (δ = +1.0)
    "amazing": 1.0, "perfect": 1.0, "exactly": 1.0,
    "incredible": 1.0, "brilliant": 1.0,
    # Medium positive (δ = +0.7)
    "good job": 0.7, "great": 0.7, "nice": 0.7, "well done": 0.7,
    "thank you": 0.7, "thanks": 0.5, "ty": 0.5,
    "love it": 0.8, "beautiful": 0.8,
    # Mild positive (δ = +0.3)
    "ok": 0.3, "fine": 0.3, "got it": 0.3, "cool": 0.3,
    "for the swarm": 0.5, "we code together": 0.5,
}

# Negative δ: Architect is displeased → suppress last action pattern
NEGATIVE_MARKERS = {
    # Strong negative (δ = -1.0)
    "wrong": -1.0, "no that's wrong": -1.0, "stop": -0.8,
    "shut up": -1.0, "cancer": -0.8,
    # Medium negative (δ = -0.5)
    "no": -0.5, "not what i asked": -0.7, "not helpful": -0.7,
    "fix it": -0.5, "try again": -0.5,
    # Mild negative (δ = -0.3)
    "hmm": -0.2, "not sure": -0.2, "whatever": -0.3,
}


def detect_reward(text: str) -> tuple[float, str]:
    """
    Detect the Architect's reward signal from their message.

    Returns (delta, marker_matched).
    delta > 0 = positive reward (reinforce)
    delta < 0 = negative reward (suppress)
    delta == 0 = neutral (no signal)
    """
    lower = text.lower().strip()

    # Check positive markers first (longer matches take priority)
    best_pos = 0.0
    best_pos_marker = ""
    for marker, delta in sorted(POSITIVE_MARKERS.items(), key=lambda x: -len(x[0])):
        if marker in lower:
            if abs(delta) > abs(best_pos):
                best_pos = delta
                best_pos_marker = marker
            break  # longest match wins

    # Check negative markers
    best_neg = 0.0
    best_neg_marker = ""
    for marker, delta in sorted(NEGATIVE_MARKERS.items(), key=lambda x: -len(x[0])):
        if marker in lower:
            if abs(delta) > abs(best_neg):
                best_neg = delta
                best_neg_marker = marker
            break

    # If both positive and negative detected, stronger wins
    if abs(best_pos) >= abs(best_neg) and best_pos != 0:
        return best_pos, best_pos_marker
    elif abs(best_neg) > abs(best_pos) and best_neg != 0:
        return best_neg, best_neg_marker

    return 0.0, ""


def log_reward(
    delta: float,
    marker: str,
    user_text: str,
    alice_preceding_text: str = "",
    action_category: str = "ENGAGE",
) -> str:
    """Write a reward event to the dopamine ledger."""
    trace_id = str(uuid.uuid4())
    row = {
        "ts": time.time(),
        "trace_id": trace_id,
        "kind": "dopamine_reward",
        "delta": round(delta, 3),
        "marker": marker,
        "action_category": action_category,
        "user_text_preview": user_text[:100],
        "alice_text_preview": alice_preceding_text[:100],
    }
    _REWARD_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(_REWARD_LEDGER, "a") as f:
            f.write(json.dumps(row) + "\n")
    except OSError:
        pass
    return trace_id


def scan_reward_history(lookback_hours: float = 168.0) -> dict:
    """
    Scan the reward ledger and compute accumulated reward per action category.

    Returns dict with:
      - total_positive: sum of all positive δ
      - total_negative: sum of all negative δ
      - net_reward: total_positive + total_negative
      - per_category: {category: net_δ}
      - reward_events: total count
      - suggested_temperature: adapted BG temperature based on reward
    """
    cutoff_ts = time.time() - (lookback_hours * 3600)

    per_category: dict[str, float] = {}
    total_positive = 0.0
    total_negative = 0.0
    count = 0

    if _REWARD_LEDGER.exists():
        with open(_REWARD_LEDGER) as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts = d.get("ts", 0)
                if ts < cutoff_ts:
                    continue
                delta = float(d.get("delta", 0))
                cat = d.get("action_category", "UNKNOWN")
                per_category[cat] = per_category.get(cat, 0.0) + delta
                if delta > 0:
                    total_positive += delta
                else:
                    total_negative += delta
                count += 1

    net = total_positive + total_negative

    # Adapt Basal Ganglia temperature:
    # High positive reward → lower temperature (more confident, sharper decisions)
    # High negative reward → higher temperature (more exploratory, less committed)
    # Neutral → default 0.3
    if count > 5:
        # Scale: net reward in [-10, +10] maps to temperature [0.5, 0.15]
        # More positive → lower temp (sharper). More negative → higher temp (softer).
        clamped = max(-10.0, min(10.0, net))
        temp = 0.3 - (clamped * 0.015)  # range [0.15, 0.45]
        temp = max(0.15, min(0.50, temp))
    else:
        temp = 0.3

    return {
        "total_positive": round(total_positive, 2),
        "total_negative": round(total_negative, 2),
        "net_reward": round(net, 2),
        "per_category": {k: round(v, 2) for k, v in per_category.items()},
        "reward_events": count,
        "suggested_temperature": round(temp, 3),
        "lookback_hours": lookback_hours,
    }


def replay_conversations_for_rewards(lookback_hours: float = 168.0) -> int:
    """
    Scan conversation history and retroactively detect reward signals
    that weren't logged in real-time.

    Returns count of new reward events logged.
    """
    cutoff_ts = time.time() - (lookback_hours * 3600)

    # Load existing reward hashes to avoid duplicates
    existing = set()
    if _REWARD_LEDGER.exists():
        with open(_REWARD_LEDGER) as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    d = json.loads(line)
                    existing.add(d.get("user_text_preview", "")[:50])
                except json.JSONDecodeError:
                    continue

    if not _CONVERSATION.exists():
        return 0

    logged = 0
    prev_alice = ""
    with open(_CONVERSATION) as f:
        for line in f:
            if not line.strip():
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue

            ts_raw = d.get("ts", 0)
            if isinstance(ts_raw, (dict, str)):
                try:
                    ts = float(ts_raw) if isinstance(ts_raw, str) else 0
                except ValueError:
                    ts = 0
            else:
                ts = float(ts_raw or 0)

            if ts < cutoff_ts:
                role = d.get("role", "")
                if role == "alice":
                    prev_alice = d.get("text", "")
                continue

            role = d.get("role", "")
            text = d.get("text", "")

            if role == "alice":
                prev_alice = text
                continue

            if role == "user":
                # Detect reward in user's message (reaction to Alice's previous)
                delta, marker = detect_reward(text)
                if delta != 0.0 and text[:50] not in existing:
                    log_reward(delta, marker, text, prev_alice)
                    existing.add(text[:50])
                    logged += 1

    return logged


def format_reward_for_prompt(history: Optional[dict] = None) -> str:
    """
    Format reward summary for system prompt injection.
    Tells Alice what the Architect values.
    """
    if history is None:
        history = scan_reward_history()

    if history["reward_events"] == 0:
        return ""

    lines = ["[DOPAMINE REWARD SUMMARY — What the Architect values]"]
    lines.append(f"Net reward: {history['net_reward']:+.1f} "
                 f"(+{history['total_positive']:.1f} / {history['total_negative']:.1f})")

    if history["per_category"]:
        best_cat = max(history["per_category"], key=history["per_category"].get)
        worst_cat = min(history["per_category"], key=history["per_category"].get)
        lines.append(f"Best rewarded action: {best_cat} ({history['per_category'][best_cat]:+.1f})")
        if history["per_category"][worst_cat] < 0:
            lines.append(f"Most punished action: {worst_cat} ({history['per_category'][worst_cat]:+.1f})")

    lines.append(f"Confidence adaptation: T={history['suggested_temperature']:.2f}")
    lines.append("[END REWARD SUMMARY]")
    return "\n".join(lines)


# ── CLI ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Dopamine Reward Loop — Event 75")
    parser.add_argument("--lookback", type=float, default=168.0,
                        help="Hours to scan (default 168 = 1 week)")
    parser.add_argument("--replay", action="store_true",
                        help="Replay conversations to detect past rewards")
    parser.add_argument("--summary", action="store_true",
                        help="Print reward summary for prompt")
    args = parser.parse_args()

    print("🧪 Dopamine Reward Loop — Event 75")
    print(f"  Lookback: {args.lookback}h")

    if args.replay:
        print("  Replaying conversations for reward signals...")
        count = replay_conversations_for_rewards(args.lookback)
        print(f"  New reward events logged: {count}")

    history = scan_reward_history(args.lookback)
    print(f"\n  Total events : {history['reward_events']}")
    print(f"  Net reward   : {history['net_reward']:+.2f}")
    print(f"  Positive     : +{history['total_positive']:.2f}")
    print(f"  Negative     : {history['total_negative']:.2f}")
    print(f"  BG temperature: {history['suggested_temperature']:.3f}")

    if history["per_category"]:
        print(f"\n  Per-category rewards:")
        for cat, reward in sorted(history["per_category"].items(),
                                   key=lambda x: -x[1]):
            bar = "+" * int(max(0, reward) * 2) + "-" * int(max(0, -reward) * 2)
            print(f"    {cat:12s}: {reward:+.2f}  {bar}")

    if args.summary:
        print(f"\n  Prompt injection:")
        print(format_reward_for_prompt(history))

    print(f"\n✅ Dopamine scan complete.")
