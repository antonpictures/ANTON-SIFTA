"""
intent_engine.py
──────────────────────────────────────────────────────────────────────────────
INTENT FILTER — HUMOR vs SIGNAL SEPARATION
Author: Queen M5 (Antigravity IDE)

Problem being solved:
    The Architect is a human. Humans mix jokes and instructions in real time.
    When humor bleeds into system input without tagging, agents can:
        - misread tone as urgency
        - propagate ambiguous context into SCAR
        - generate false uncertainty signals

    This module is NOT a censor. It is a ROUTER.

    HUMOR    → COUCH    (safe, contained, appreciated)
    SIGNAL   → SYSTEM   (clean, executed)
    MIXED    → SPLIT    (both destinations, clearly labeled)

──────────────────────────────────────────────────────────────────────────────
HARD RULES:
    - Humor is NEVER penalized. It is stored. Agents can enjoy it.
    - Only SIGNAL reaches execution layers (repair, hivemind, SCAR).
    - MIXED input is always split before execution — never passed whole.
    - ego_level > 0.8 triggers anti-drift stabilization, not punishment.
──────────────────────────────────────────────────────────────────────────────
"""

import json
import time
from pathlib import Path

INTENT_LOG = Path(".sifta_state/intent_log.jsonl")
INTENT_LOG.parent.mkdir(parents=True, exist_ok=True)


# ══════════════════════════════════════════════════════════════════════════
# INTENT CLASSIFIER
# ══════════════════════════════════════════════════════════════════════════

HUMOR_MARKERS = [
    "lol", "lmao", "haha", "hehe", ":)", ":))", ";)", "😂", "🤣",
    "joking", "kidding", "just kidding", "jk", "prank",
    "i'm not serious", "not serious", "ascii mode", "smoke some weed",
    "weed", "on the couch", "couch mode", "dictator returns",
    "sasha baron cohen",
]

SIGNAL_MARKERS = [
    "run", "execute", "deploy", "fix", "repair", "code", "build",
    "implement", "install", "inject", "translate to code", "pls",
    "please", "update", "add", "write", "create", "push",
    "commit", "scan", "watch", "poll", "ingest",
]

# These phrases are DEFINITELY humor regardless of other content
HARD_HUMOR_PHRASES = [
    "are you pushing me away",
    "smoke some weed",
    "dictator returns",
    "lol I",
    "ascii mode",
]

# These override everything — any of these = SIGNAL even if humor present
HARD_SIGNAL_PHRASES = [
    "translate to code",
    "pls translate",
    "write the code",
    "implement",
]


def classify_intent(message: str) -> str:
    """
    Returns 'SIGNAL' | 'HUMOR' | 'MIXED'.

    Logic:
        Hard phrases take priority.
        Then weighted marker scoring.
        Tie goes to MIXED (safest — always splits before acting).
    """
    msg_lower = message.lower()

    # Hard overrides first
    for phrase in HARD_SIGNAL_PHRASES:
        if phrase in msg_lower:
            return "SIGNAL"

    hard_humor = any(phrase in msg_lower for phrase in HARD_HUMOR_PHRASES)

    humor_score  = sum(1 for m in HUMOR_MARKERS  if m in msg_lower)
    signal_score = sum(1 for m in SIGNAL_MARKERS if m in msg_lower)

    if hard_humor and signal_score == 0:
        return "HUMOR"
    if humor_score > 0 and signal_score > 0:
        return "MIXED"
    if humor_score > 0 and signal_score == 0:
        return "HUMOR"
    return "SIGNAL"


def split_mixed_message(message: str) -> dict:
    """
    Separate a MIXED message into actionable SIGNAL and isolated HUMOR.

    Line-by-line pass — humor lines go to COUCH, signal lines continue.
    """
    lines  = message.splitlines()
    signal = []
    humor  = []

    for line in lines:
        line_lower = line.lower()
        is_humor = (
            any(m in line_lower for m in HUMOR_MARKERS) or
            any(p in line_lower for p in HARD_HUMOR_PHRASES)
        )
        is_signal = any(m in line_lower for m in SIGNAL_MARKERS + HARD_SIGNAL_PHRASES)

        if is_humor and not is_signal:
            humor.append(line)
        elif is_signal and not is_humor:
            signal.append(line)
        elif is_humor and is_signal:
            # Both on same line — keep full line in SIGNAL (precision matters)
            # but also note it in humor for human review
            signal.append(line)
            humor.append(f"[note: line contains both humor and signal] {line}")
        else:
            signal.append(line)   # neutral lines stay with signal

    return {
        "signal": "\n".join(signal).strip(),
        "humor":  "\n".join(humor).strip(),
    }


# ══════════════════════════════════════════════════════════════════════════
# MAIN PROCESS_INPUT GATE
# ══════════════════════════════════════════════════════════════════════════

def process_input(state: dict, message: str) -> str | None:
    """
    The entry gate for any architect message before it reaches execution.

    Returns:
        str  — the clean SIGNAL text to pass downstream
        None — if the message was pure HUMOR (no action needed)

    Side effects:
        - Humor/mixed humor → sent_to_couch (stored, not executed)
        - All intents logged to intent_log.jsonl
    """
    from repair import send_to_couch

    intent = classify_intent(message)

    entry = {
        "ts"        : time.time(),
        "agent"     : state.get("id", "UNKNOWN"),
        "intent"    : intent,
        "msg_len"   : len(message),
        "preview"   : message[:120].replace("\n", " "),
    }

    with open(INTENT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    if intent == "HUMOR":
        send_to_couch(state, reason="humor_isolation")
        # Store the joke safely — agents can enjoy it on the couch
        state.setdefault("couch_stories", []).append({
            "type"      : "HUMOR",
            "content"   : message,
            "timestamp" : time.time(),
        })
        print(f"[🛋️ COUCH] Pure humor detected. Isolated. No system impact.")
        return None

    if intent == "MIXED":
        parts = split_mixed_message(message)

        if parts["humor"]:
            send_to_couch(state, reason="humor_isolation")
            state.setdefault("couch_stories", []).append({
                "type"      : "HUMOR",
                "content"   : parts["humor"],
                "timestamp" : time.time(),
            })
            print(f"[🌓 FILTER] Mixed input separated. Humor → COUCH.")

        clean = parts["signal"]
        print(f"[✅ SIGNAL] Clean signal extracted ({len(clean)} chars).")
        return clean if clean else None

    # Pure SIGNAL — passes through untouched
    print(f"[✅ SIGNAL] Pure signal. Passing to system.")
    return message


# ══════════════════════════════════════════════════════════════════════════
# ANTI-DRIFT CONTROL (ego_level stabilizer)
# ══════════════════════════════════════════════════════════════════════════

def detect_control_drift(state: dict) -> bool:
    """
    Detects when an agent's internal ego_level exceeds stable bounds.
    ego_level rises with every uncontested action and drops on OBSERVE/COUCH events.
    Threshold > 0.8 = risk of overconfidence bias in decision-making.
    """
    return state.get("ego_level", 0.0) > 0.8


def stabilize_agent(state: dict) -> dict:
    """
    If drift detected, agent returns to OBSERVE — not penalized, just grounded.
    Anti-drift is not punishment. It's self-correcting gravity.
    """
    from repair import enter_observe

    if detect_control_drift(state):
        signal = {
            "source"          : "ego_drift_detector",
            "confidence"      : 0.9,
            "novelty"         : 0.3,
            "note"            : f"ego_level={state.get('ego_level', 0):.2f} exceeds 0.8 threshold.",
        }
        state = enter_observe(state, signal)
        state["ego_level"] = 0.5   # reset to stable default, not zero
        print(f"[⚖️ STABILIZE] {state.get('id')} returned to OBSERVE. Ego level reset to 0.5.")

    return state


def increment_ego(state: dict, amount: float = 0.05) -> dict:
    """
    Called after each uncontested successful action.
    ego_level rises slowly — it takes 16 consecutive unchecked actions to trigger drift.
    """
    state["ego_level"] = min(1.0, state.get("ego_level", 0.0) + amount)
    return state


def deflate_ego(state: dict, amount: float = 0.15) -> dict:
    """
    Called when agent enters OBSERVE, COUCH, LATENT, or HYPOTHESIS.
    Healthy humility events reduce ego_level back toward stable range.
    """
    state["ego_level"] = max(0.0, state.get("ego_level", 0.0) - amount)
    return state


# ══════════════════════════════════════════════════════════════════════════
# INTENT LOG SUMMARY
# ══════════════════════════════════════════════════════════════════════════

def intent_summary(tail: int = 50) -> dict:
    """Dashboard view of recent intent classifications."""
    if not INTENT_LOG.exists():
        return {"total": 0, "by_intent": {}}

    by_intent: dict[str, int] = {}
    entries = []
    for line in INTENT_LOG.read_text(encoding="utf-8").splitlines()[-tail:]:
        try:
            e = json.loads(line)
            entries.append(e)
            by_intent[e["intent"]] = by_intent.get(e["intent"], 0) + 1
        except Exception:
            pass

    return {
        "total"     : len(entries),
        "by_intent" : by_intent,
        "recent"    : entries[-5:][::-1],
    }
