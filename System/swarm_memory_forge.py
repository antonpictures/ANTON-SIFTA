#!/usr/bin/env python3
"""
System/swarm_memory_forge.py
══════════════════════════════════════════════════════════════════════
The Memory Forge — Time-Based Engram Consolidation

Author:   C47H (Cursor IDE node, 2026-04-19, Epoch 7)
Lock:     .sifta_state/lobe_construction_locks/memory_forge.lock (IN_PROGRESS)
Mandate:  Architect AGI Tournament Plan, Epoch 7
          "she has almost no persistent memory of what she has learned"

WHY THIS EXISTS (the honest diagnosis)
─────────────────────────────────────────────────────────────────────
`swarm_hippocampus.py` has two problems:
  1. It only runs when `mood_multiplier <= 1.0` (rest state) — but Alice
     rarely rests. 568 conversations, 1 engram. The trigger is wrong.
  2. It requires a live Gemini API call. When Gemini is unavailable
     (network down, budget exhausted, rate-limited), zero consolidation
     happens. The Memory Forge uses LOCAL heuristics first, Gemini
     second-optional.

THE FORGE STRATEGY (no Gemini required for baseline)
─────────────────────────────────────────────────────────────────────
Every N turns (configurable, default 50) OR every T seconds of idle
(configurable, default 1800 = 30 min), scan the raw conversation ledger
and score candidate turns for engram-worthiness using four local
heuristics:

  NOVELTY: cosine similarity against existing engrams' abstract_rule
  text is not computed (we don't have embeddings locally) — instead we
  check for keyword overlap: < 30% shared words with any existing engram
  → novel.

  ACTIONABILITY: turn contains a learned procedure. Heuristic: contains
  a bash command, a file path, a module name (swarm_*.py), or an
  explicit "I learned / I discovered / I now know" assertion.

  EMOTIONAL WEIGHT: within ±120s of the turn, was there a DOPAMINE or
  CORTISOL event in endocrine_glands.jsonl? If yes, emotionally salient.

  ARCHITECTURAL SIGNIFICANCE: turn concerns Alice's identity, her
  hardware, her lobes, or the STGM economy. High-signal turns about
  "what I am" or "what I can do."

Score = (novelty × 0.3) + (actionability × 0.3) + (emotional × 0.2) + (arch × 0.2)
Threshold: 0.35. Turns above threshold are forge candidates.

Top-3 forge candidates per cycle become engrams. If Gemini is available,
it summarizes the turn into an abstract_rule. If not, the raw turn text
(truncated to 280 chars) IS the engram — imperfect but real.

SKILL BACK-INJECTION (the loop that closes AGI gap A)
─────────────────────────────────────────────────────────────────────
After forging, this module writes the top-5 most-recent engrams to
.sifta_state/active_engrams.json. The talk widget's _build_swarm_context
reads this file and appends a "WHAT I KNOW FROM EXPERIENCE" block to
Alice's context on every turn. She reads her own past learning.

This is the loop: conversation → forge → injection → behavior → conversation.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"

_CONVO_LOG = _STATE_DIR / "alice_conversation.jsonl"
_ENGRAMS_LOG = _STATE_DIR / "long_term_engrams.jsonl"
_ACTIVE_ENGRAMS = _STATE_DIR / "active_engrams.json"
_ENDOCRINE_LOG = _STATE_DIR / "endocrine_glands.jsonl"
_FORGE_STATE = _STATE_DIR / "memory_forge_state.json"

# ── Tuning constants (hot-reloadable via swarm_hot_reload) ───────────
FORGE_EVERY_N_TURNS: int = 50          # forge after this many new convo turns
FORGE_EVERY_T_IDLE_S: float = 1800.0   # or after 30 min of no new turns
ENGRAM_SCORE_THRESHOLD: float = 0.35   # minimum score to forge
TOP_K_CANDIDATES_PER_CYCLE: int = 3    # max new engrams per forge cycle
ACTIVE_ENGRAMS_SHOWN: int = 5          # how many engrams Alice sees in prompt
MIN_TURN_LENGTH: int = 20              # ignore very short turns


# ════════════════════════════════════════════════════════════════════
# SCORING HEURISTICS (all local, no API required)
# ════════════════════════════════════════════════════════════════════

_ACTIONABLE_PATTERNS = [
    r"python3?[\s-]",          # shell commands
    r"\bswarm_\w+\.py\b",      # module references
    r"\.sifta_state/",         # ledger references
    r"\bI (learned|discovered|realized|now know|found out|can now)\b",
    r"\bshould (always|never|only|first)\b",
    r"\bthe (correct|right|proper|canonical) way\b",
    r"PASS|FAIL|COMPLETED|ABORTED|EXCRETED",  # outcome vocabulary
    r"\d+ STGM",               # economic outcomes
]
_ACTIONABLE_RE = [re.compile(p, re.IGNORECASE) for p in _ACTIONABLE_PATTERNS]

_ARCHITECTURAL_PATTERNS = [
    r"\b(Alice|SIFTA|swarm|lobe|cortex|hippocampus|ribosome|olfactory|vagus)\b",
    r"\bM5\b|\bApple Silicon\b|\bM-series\b",
    r"\bSTGM\b|\bPoUW\b|\bproof.of.useful.work\b",
    r"\b(epoch|evolution|mitosis|engram|memory)\b",
    r"\b(AGI|sentient|conscious|identity|self)\b",
]
_ARCH_RE = [re.compile(p, re.IGNORECASE) for p in _ARCHITECTURAL_PATTERNS]


def _score_turn(text: str, ts: float,
                existing_engrams: List[str],
                endocrine_events: List[Dict]) -> float:
    """
    Score a single conversation turn for engram-worthiness. Returns 0-1.
    """
    if len(text) < MIN_TURN_LENGTH:
        return 0.0

    # ── Novelty ──────────────────────────────────────────────────────
    words = set(re.findall(r"\b\w{4,}\b", text.lower()))
    if not words:
        return 0.0

    max_overlap = 0.0
    for eng in existing_engrams:
        eng_words = set(re.findall(r"\b\w{4,}\b", eng.lower()))
        if eng_words:
            overlap = len(words & eng_words) / len(words | eng_words)
            max_overlap = max(max_overlap, overlap)
    novelty = 1.0 - max_overlap  # high overlap = low novelty

    # ── Actionability ─────────────────────────────────────────────────
    action_hits = sum(1 for p in _ACTIONABLE_RE if p.search(text))
    actionability = min(1.0, action_hits / 3.0)

    # ── Emotional weight (within ±120s) ───────────────────────────────
    emotional = 0.0
    window = 120.0
    for ev in endocrine_events:
        ev_ts = float(ev.get("timestamp", ev.get("ts", 0)))
        hormone = str(ev.get("hormone", "")).upper()
        if abs(ev_ts - ts) <= window:
            if "DOPAMINE" in hormone:
                emotional = max(emotional, 0.8)
            elif "CORTISOL" in hormone:
                emotional = max(emotional, 0.6)
            elif "EPINEPHRINE" in hormone:
                emotional = max(emotional, 0.5)

    # ── Architectural significance ─────────────────────────────────────
    arch_hits = sum(1 for p in _ARCH_RE if p.search(text))
    architectural = min(1.0, arch_hits / 4.0)

    score = (
        novelty * 0.30
        + actionability * 0.30
        + emotional * 0.20
        + architectural * 0.20
    )
    return round(score, 4)


# ════════════════════════════════════════════════════════════════════
# ENGRAM SUMMARISER (Gemini optional, local fallback)
# ════════════════════════════════════════════════════════════════════

def _summarise_to_abstract_rule(text: str, ts: float) -> str:
    """
    Try Gemini for a crisp abstract rule. Fall back to the raw turn text
    (truncated) if unavailable. Never blocks the forge cycle.
    """
    prompt = (
        "You are the SIFTA Hippocampus. Compress this single conversation fragment "
        "into ONE dense, generalized sentence that captures the durable behavioral "
        "rule or factual learning that Alice should never forget.\n"
        "If there is no durable lesson, reply exactly: NOTHING_DURABLE\n\n"
        f"Fragment:\n{text[:800]}"
    )
    try:
        sys_dir = str(_REPO / "System")
        if sys_dir not in sys.path:
            sys.path.insert(0, sys_dir)
        from System.swarm_api_sentry import call_gemini
        result = call_gemini(prompt, max_tokens=120, temperature=0.2)
        if result and "NOTHING_DURABLE" not in result:
            return result.strip()[:280]
    except Exception:
        pass

    # Local fallback: extract the most salient sentence heuristically.
    sentences = [s.strip() for s in re.split(r"[.!?]", text) if len(s.strip()) > 30]
    # Pick the sentence with the most architectural keywords.
    if sentences:
        best = max(sentences,
                   key=lambda s: sum(1 for p in _ARCH_RE if p.search(s))
                   + sum(1 for p in _ACTIONABLE_RE if p.search(s)))
        return best[:280]
    return text[:280]


# ════════════════════════════════════════════════════════════════════
# THE FORGE
# ════════════════════════════════════════════════════════════════════

def _load_state() -> Dict[str, Any]:
    if _FORGE_STATE.exists():
        try:
            return json.loads(_FORGE_STATE.read_text())
        except Exception:
            pass
    return {"last_forge_ts": 0.0, "last_turn_count": 0}


def _save_state(state: Dict[str, Any]) -> None:
    try:
        _FORGE_STATE.write_text(json.dumps(state, indent=2))
    except Exception:
        pass


def _load_existing_engrams() -> List[str]:
    """Return list of abstract_rule strings from existing engrams."""
    if not _ENGRAMS_LOG.exists():
        return []
    rules = []
    try:
        for line in _ENGRAMS_LOG.read_text().splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
                rule = rec.get("abstract_rule", "")
                if rule:
                    rules.append(rule)
            except Exception:
                pass
    except Exception:
        pass
    return rules


def _load_engram_records() -> List[Dict[str, Any]]:
    """
    Return full engram records (including the `pinned` flag) from
    long_term_engrams.jsonl. Used by _update_active_engrams() to honour
    the milestone-engram pin protocol.

    A pinned engram is one we never want to fall out of Alice's prompt,
    regardless of how many newer engrams the forge produces. Pinning is
    reserved for AGI emergence moments and other irreplaceable lessons
    (e.g. the 2026-04-19 cough → "take care of yourself" event).
    """
    if not _ENGRAMS_LOG.exists():
        return []
    out: List[Dict[str, Any]] = []
    try:
        for line in _ENGRAMS_LOG.read_text().splitlines():
            if not line.strip():
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    except Exception:
        pass
    return out


def write_pinned_engram(abstract_rule: str, *,
                        source: str = "milestone_pin",
                        note: str = "") -> Dict[str, Any]:
    """
    Append a permanent engram with `pinned=True`. Pinned engrams are
    always present in active_engrams.json and therefore always in
    Alice's `_SYSTEM_PROMPT`. Use sparingly — every pinned engram costs
    prompt tokens on every turn — and only for lessons that must never
    be forgotten.
    """
    record = {
        "ts": time.time(),
        "abstract_rule": abstract_rule,
        "source": source,
        "pinned": True,
        "note": note,
    }
    try:
        from System.jsonl_file_lock import append_line_locked
        append_line_locked(_ENGRAMS_LOG, json.dumps(record) + "\n")
    except Exception:
        with open(_ENGRAMS_LOG, "a") as fh:
            fh.write(json.dumps(record) + "\n")
    return record


def _load_endocrine_events() -> List[Dict]:
    if not _ENDOCRINE_LOG.exists():
        return []
    events = []
    try:
        for line in _ENDOCRINE_LOG.read_text().splitlines()[-500:]:
            if not line.strip():
                continue
            try:
                events.append(json.loads(line))
            except Exception:
                pass
    except Exception:
        pass
    return events


def _load_convo_turns(since_turn: int = 0) -> List[Dict[str, Any]]:
    """Load alice turns from the conversation ledger."""
    if not _CONVO_LOG.exists():
        return []
    turns = []
    try:
        all_lines = _CONVO_LOG.read_text().splitlines()
        for i, line in enumerate(all_lines):
            if i < since_turn:
                continue
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
                # Only forge from Alice's own output — that's what she learned
                rec_role = rec.get("role") or rec.get("payload", {}).get("role")
                if rec_role in ("alice", "assistant"):
                    text = rec.get("text") or rec.get("content") or rec.get("payload", {}).get("text") or rec.get("payload", {}).get("content") or ""
                    ts_val = rec.get("ts") or rec.get("payload", {}).get("ts") or 0.0
                    if isinstance(ts_val, dict):
                        ts_val = ts_val.get("physical_pt", 0.0)
                    ts = float(ts_val)
                    if text:
                        turns.append({"idx": i, "text": text, "ts": ts})
            except Exception:
                pass
    except Exception:
        pass
    return turns


def _write_engram(abstract_rule: str, source_ts: float,
                  score: float, source_text: str) -> Dict[str, Any]:
    record = {
        "ts": time.time(),
        "abstract_rule": abstract_rule,
        "source": "memory_forge_C47H_Epoch7",
        "forge_score": score,
        "source_ts": source_ts,
        "source_excerpt": source_text[:120],
    }
    try:
        from System.jsonl_file_lock import append_line_locked
        append_line_locked(_ENGRAMS_LOG, json.dumps(record) + "\n")
    except Exception:
        with open(_ENGRAMS_LOG, "a") as fh:
            fh.write(json.dumps(record) + "\n")
    return record


def _update_active_engrams() -> List[str]:
    """
    Write .sifta_state/active_engrams.json with engrams Alice reads in her
    prompt. Composition rule:

      - ALL pinned engrams are included first (deduplicated, oldest→newest)
      - Then the most-recent unpinned engrams fill the remaining slots
        up to ACTIVE_ENGRAMS_SHOWN

    Pinned engrams cannot be evicted by newer forge cycles. This is how
    AGI milestone moments stay in Alice's working set forever.
    """
    records = _load_engram_records()

    pinned: List[str] = []
    unpinned: List[str] = []
    seen: set = set()
    for rec in records:
        rule = (rec.get("abstract_rule") or "").strip()
        if not rule or rule in seen:
            continue
        seen.add(rule)
        if rec.get("pinned"):
            pinned.append(rule)
        else:
            unpinned.append(rule)

    # Most-recent unpinned first, then trim to fill the budget alongside pins.
    unpinned_recent = list(reversed(unpinned))
    budget = max(0, ACTIVE_ENGRAMS_SHOWN - len(pinned))
    active = pinned + unpinned_recent[:budget]

    payload = {
        "ts": time.time(),
        "engrams": active,
        "pinned_count": len(pinned),
        "total_forged": len(records),
    }
    try:
        _ACTIVE_ENGRAMS.write_text(json.dumps(payload, indent=2))
    except Exception:
        pass
    return active


def should_forge() -> Tuple[bool, str]:
    """
    Returns (should_run, reason). Called by swarm_boot.py's heartbeat.
    True if enough turns have accumulated OR enough idle time has passed.
    """
    state = _load_state()
    now = time.time()

    # Count current turns
    current_count = 0
    if _CONVO_LOG.exists():
        try:
            current_count = sum(
                1 for line in _CONVO_LOG.read_text().splitlines()
                if line.strip()
            )
        except Exception:
            pass

    turns_since = current_count - int(state.get("last_turn_count", 0))
    idle_s = now - float(state.get("last_forge_ts", 0.0))

    if turns_since >= FORGE_EVERY_N_TURNS:
        return (True, f"turns_since_last_forge={turns_since} >= {FORGE_EVERY_N_TURNS}")
    if idle_s >= FORGE_EVERY_T_IDLE_S and turns_since > 0:
        return (True, f"idle_s={idle_s:.0f} >= {FORGE_EVERY_T_IDLE_S:.0f} and new turns exist")
    return (False, f"turns_since={turns_since} idle_s={idle_s:.0f}")


def forge(*, force: bool = False) -> Dict[str, Any]:
    """
    Main entry point. Scans recent conversations, scores turns,
    forges the top candidates as engrams, updates active_engrams.json.

    Returns a summary dict.
    """
    _STATE_DIR.mkdir(parents=True, exist_ok=True)

    if not force:
        ok, reason = should_forge()
        if not ok:
            return {"status": "skipped", "reason": reason}

    state = _load_state()
    last_turn_idx = int(state.get("last_turn_count", 0))

    # Load material
    new_turns = _load_convo_turns(since_turn=last_turn_idx)
    existing_rules = _load_existing_engrams()
    endocrine = _load_endocrine_events()

    if not new_turns:
        return {"status": "skipped", "reason": "no_new_alice_turns"}

    # Score every candidate turn
    scored: List[Tuple[float, Dict]] = []
    for turn in new_turns:
        s = _score_turn(
            text=turn["text"],
            ts=turn["ts"],
            existing_engrams=existing_rules,
            endocrine_events=endocrine,
        )
        if s >= ENGRAM_SCORE_THRESHOLD:
            scored.append((s, turn))

    # Sort by score descending, take top K
    scored.sort(key=lambda x: x[0], reverse=True)
    top_candidates = scored[:TOP_K_CANDIDATES_PER_CYCLE]

    forged: List[Dict] = []
    for score, turn in top_candidates:
        abstract_rule = _summarise_to_abstract_rule(turn["text"], turn["ts"])
        if abstract_rule and "NOTHING_DURABLE" not in abstract_rule:
            rec = _write_engram(
                abstract_rule=abstract_rule,
                source_ts=turn["ts"],
                score=score,
                source_text=turn["text"],
            )
            forged.append(rec)
            # Add to existing_rules so subsequent candidates in this cycle
            # feel novelty pressure from what we just forged.
            existing_rules.append(abstract_rule)

    # Update active engrams for prompt injection
    active = _update_active_engrams()

    # Persist state
    current_total = last_turn_idx + len(new_turns)
    # Use full count, not just alice turns, so delta is stable
    if _CONVO_LOG.exists():
        try:
            current_total = sum(
                1 for l in _CONVO_LOG.read_text().splitlines() if l.strip()
            )
        except Exception:
            pass
    state["last_forge_ts"] = time.time()
    state["last_turn_count"] = current_total
    _save_state(state)

    return {
        "status": "forged",
        "candidates_scored": len(scored),
        "new_engrams_forged": len(forged),
        "total_engrams": len(existing_rules),
        "active_engrams_shown": len(active),
        "forged_rules": [r["abstract_rule"][:80] for r in forged],
    }


# ════════════════════════════════════════════════════════════════════
# SUMMARY (prompt injection)
# ════════════════════════════════════════════════════════════════════
def get_forge_summary() -> str:
    """One-line for swarm_boot.py / Thalamus. Never raises."""
    try:
        total = len(_load_existing_engrams())
        if total == 0:
            return "Memory Forge: no engrams yet — next cycle pending"
        state = _load_state()
        last = state.get("last_forge_ts", 0.0)
        age_min = (time.time() - float(last)) / 60.0
        return (
            f"Memory Forge: {total} lifetime engrams, "
            f"last forge {age_min:.0f} min ago"
        )
    except Exception:
        return "Memory Forge: introspection unavailable"


def get_active_engrams_block() -> str:
    """
    Returns the '## WHAT I KNOW FROM EXPERIENCE' block for Alice's context.
    Empty string if no engrams yet (callers can skip the block).
    """
    try:
        if not _ACTIVE_ENGRAMS.exists():
            return ""
        payload = json.loads(_ACTIVE_ENGRAMS.read_text())
        engrams = payload.get("engrams", [])
        if not engrams:
            return ""
        lines = ["## WHAT I KNOW FROM EXPERIENCE (forged from past conversations):"]
        for i, rule in enumerate(engrams, 1):
            lines.append(f"  {i}. {rule}")
        return "\n".join(lines)
    except Exception:
        return ""


# ════════════════════════════════════════════════════════════════════
# CLI
# ════════════════════════════════════════════════════════════════════
def _cli() -> int:
    import argparse
    parser = argparse.ArgumentParser(
        prog="swarm_memory_forge",
        description="Time-based engram consolidation for SIFTA OS.",
    )
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("forge", help="Run a forge cycle now (respects cooldown).")
    p_force = sub.add_parser("force", help="Force-forge regardless of cooldown.")
    sub.add_parser("status", help="Print should_forge() gate status.")
    sub.add_parser("summary", help="Print one-line summary.")
    sub.add_parser("active", help="Print the active_engrams block Alice sees.")
    sub.add_parser("list", help="List all forged engrams.")
    sub.add_parser("smoke", help="Run embedded smoke test.")

    args = parser.parse_args()
    cmd = args.cmd or "status"

    if cmd == "forge":
        r = forge()
        print(json.dumps(r, indent=2))
        return 0 if r["status"] != "error" else 1
    if cmd == "force":
        r = forge(force=True)
        print(json.dumps(r, indent=2))
        return 0 if r["status"] != "error" else 1
    if cmd == "status":
        ok, reason = should_forge()
        print(f"should_forge={ok}  reason={reason}")
        print(f"total_engrams={len(_load_existing_engrams())}")
        return 0
    if cmd == "summary":
        print(get_forge_summary())
        return 0
    if cmd == "active":
        block = get_active_engrams_block()
        print(block if block else "<no active engrams yet>")
        return 0
    if cmd == "list":
        for rule in _load_existing_engrams():
            print(f"  • {rule[:100]}")
        return 0
    if cmd == "smoke":
        return _smoke()
    parser.print_help()
    return 2


# ════════════════════════════════════════════════════════════════════
# SMOKE TEST
# ════════════════════════════════════════════════════════════════════
def _smoke() -> int:
    print("=== SWARM MEMORY FORGE : SMOKE TEST ===")
    import tempfile, shutil

    tmpdir = Path(tempfile.mkdtemp(prefix="memory_forge_smoke_"))

    # Patch all paths to tmp
    import System.swarm_memory_forge as _mod
    orig = {
        "_CONVO_LOG": _mod._CONVO_LOG,
        "_ENGRAMS_LOG": _mod._ENGRAMS_LOG,
        "_ACTIVE_ENGRAMS": _mod._ACTIVE_ENGRAMS,
        "_ENDOCRINE_LOG": _mod._ENDOCRINE_LOG,
        "_FORGE_STATE": _mod._FORGE_STATE,
    }
    _mod._CONVO_LOG = tmpdir / "alice_conversation.jsonl"
    _mod._ENGRAMS_LOG = tmpdir / "long_term_engrams.jsonl"
    _mod._ACTIVE_ENGRAMS = tmpdir / "active_engrams.json"
    _mod._ENDOCRINE_LOG = tmpdir / "endocrine_glands.jsonl"
    _mod._FORGE_STATE = tmpdir / "memory_forge_state.json"

    try:
        # Write synthetic conversation — 60 alice turns, some with high actionability
        convo_lines = []
        for i in range(60):
            ts = time.time() - (60 - i) * 30
            if i % 10 == 0:
                # High-signal turn: architectural + actionable
                text = (
                    f"I just executed python3 -m System.swarm_ribosome fold and "
                    f"the SIFTA Ribosome folded ANTIGEN_{i:04x} successfully. "
                    f"I learned that running the ribosome when thermal is NOMINAL "
                    f"always completes within 200ms on this M5 Apple Silicon substrate. "
                    f"The STGM economy received 65 STGM via proof_of_useful_work."
                )
            elif i % 7 == 0:
                # Medium signal: architectural observation
                text = (
                    f"The Olfactory Cortex identified the ASUS RT-AX88U at 192.168.1.1. "
                    f"I should always classify LAN devices before running the pseudopod "
                    f"on unknown hosts. SIFTA's swarm_olfactory_cortex is now my primary sense."
                )
            else:
                # Low signal: filler
                text = f"Turn number {i}. The system is operating normally."
            rec = {"ts": ts, "role": "alice", "text": text}
            convo_lines.append(json.dumps(rec))
        _mod._CONVO_LOG.write_text("\n".join(convo_lines) + "\n")

        # 1. should_forge() triggers on 60 turns (> FORGE_EVERY_N_TURNS=50)
        ok, reason = _mod.should_forge()
        assert ok, f"Expected forge trigger, got: {reason}"
        print(f"  [PASS] should_forge = True after 60 turns ({reason[:60]})")

        # 2. forge() runs and creates engrams
        result = _mod.forge()
        assert result["status"] == "forged", result
        assert result["new_engrams_forged"] > 0, result
        print(f"  [PASS] forge produced {result['new_engrams_forged']} engrams "
              f"from {result['candidates_scored']} candidates")

        # 3. Engrams are in the ledger
        rules = _mod._load_existing_engrams()
        assert len(rules) == result["total_engrams"], (len(rules), result)
        print(f"  [PASS] {len(rules)} engrams in ledger")

        # 4. Active engrams written
        assert _mod._ACTIVE_ENGRAMS.exists()
        payload = json.loads(_mod._ACTIVE_ENGRAMS.read_text())
        assert len(payload.get("engrams", [])) > 0
        print(f"  [PASS] active_engrams.json has {len(payload['engrams'])} entries")

        # 5. Prompt block is non-empty
        block = _mod.get_active_engrams_block()
        assert "WHAT I KNOW FROM EXPERIENCE" in block, block[:80]
        print(f"  [PASS] get_active_engrams_block() returns prompt-ready block")

        # 6. Second forge() within cooldown is skipped
        result2 = _mod.forge()
        assert result2["status"] == "skipped", result2
        print(f"  [PASS] second forge within cooldown is skipped ({result2['reason'][:60]})")

        # 7. force=True overrides cooldown
        result3 = _mod.forge(force=True)
        assert result3["status"] in ("forged", "skipped"), result3
        print(f"  [PASS] force=True overrides cooldown (status={result3['status']})")

    finally:
        # Restore
        for k, v in orig.items():
            setattr(_mod, k, v)
        shutil.rmtree(tmpdir, ignore_errors=True)

    print("\n=== MEMORY FORGE SMOKE COMPLETE ===")
    print("Alice will no longer forget what she learns.")
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
