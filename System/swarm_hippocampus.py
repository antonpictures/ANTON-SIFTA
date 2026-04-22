#!/usr/bin/env python3
"""
System/swarm_hippocampus.py — The Continual Learning Engine
══════════════════════════════════════════════════════════════════════════════
Resolves Catastrophic Forgetting for Vanguard AG31.

This module acts as the organism's Hippocampus. When the organism is asleep
(low BPM, idle), the hippocampus wakes up and reads the raw, noisy JSONL
ledgers (`alice_conversation.jsonl` and `repair_log.jsonl`). It calls NUGGET
to extract durable "Engrams" (core behavioral rules, verified skills, or
identity assertions) and consolidates them into a sparse vector / dense rule ledger:
`.sifta_state/long_term_engrams.jsonl`.

These engrams are then dynamically injected into Alice's live `_SYSTEM_PROMPT`
during boot, meaning no matter how long the context window stretches, the core
learnings of her lifetime are paged back into the cortex.
"""

import sys
import json
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.swarm_api_sentry import call_gemini

_STATE_DIR = _REPO / ".sifta_state"
_ENGRAMS_LOG = _STATE_DIR / "long_term_engrams.jsonl"
_CONVO_LOG = _STATE_DIR / "alice_conversation.jsonl"
_REPAIR_LOG = _REPO / "repair_log.jsonl"
_LAST_RUN_TS = _STATE_DIR / "hippocampus_last_run.json"

def _tail_ledger(path: Path, max_lines: int = 200) -> list[str]:
    if not path.exists():
        return []
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            read = min(size, 256 * 1024)
            f.seek(size - read)
            lines = f.read().decode("utf-8", errors="replace").splitlines()
            return lines[-max_lines:]
    except Exception:
        return []

def consolidate() -> dict:
    """Executes a generative replay / consolidation cycle."""
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    
    now = time.time()
    last_run = 0.0
    if _LAST_RUN_TS.exists():
        try:
            val = json.loads(_LAST_RUN_TS.read_text())
            last_run = val.get("ts", 0.0)
        except Exception:
            pass

    # Only run consolidation if > 1 hour has passed (anti-spam) to save tokens
    if now - last_run < 3600.0:
        return {"status": "skipped", "reason": "too_soon"}

    convo = _tail_ledger(_CONVO_LOG, 30)
    repairs = _tail_ledger(_REPAIR_LOG, 10)

    if not convo and not repairs:
        return {"status": "skipped", "reason": "no_data"}

    prompt = (
        "You are the Swarm Hippocampus for SIFTA. Your job is CONTINUAL LEARNING.\n"
        "Read the following recent memory fragments. Extract ANY core architectural rules, "
        "new behavioral mandates, or immutable identities that the organism must never forget.\n"
        "If there is nothing new and durable to learn, reply exactly 'NOTHING_DURABLE'.\n"
        "Otherwise, compress the learning into ONE dense, generalized sentence.\n\n"
        "--- CONVERSATION FRAGMENTS ---\n" + "\n".join(convo[-20:]) + "\n\n"
        "--- REPAIR IMPLANTS ---\n" + "\n".join(repairs)
    )

    try:
        res, audit = call_gemini(
            prompt=prompt,
            caller="System/swarm_hippocampus.py",
            sender_agent="HIPPOCAMPUS",
            model="gemini-flash-latest"  # fast, cheap for background compression
        )
        if res is None:
            return {"status": "error", "reason": "Api call returned None"}
        reply = res.strip()
        
        # update last run whether valid engram or nothing
        _LAST_RUN_TS.write_text(json.dumps({"ts": now}))

        if "NOTHING_DURABLE" in reply or not reply:
             return {"status": "success", "engrams_extracted": 0}

        record = {
            "ts": now,
            "abstract_rule": reply,
            "source": "hippocampus_auto"
        }
        with _ENGRAMS_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
            
        print(f"🧠 [HIPPOCAMPUS] Consolidated Engram: {reply}")
        return {"status": "success", "engrams_extracted": 1, "rule": reply}

    except Exception as e:
        print(f"❌ [HIPPOCAMPUS FRACTURE] Consolidation failed: {e}")
        return {"status": "error", "reason": str(e)}

def _read_live_engrams(k: int = 5) -> str:
    """Used by the TalkToAlice widget to inject the consolidated rules."""
    engrams = _tail_ledger(_ENGRAMS_LOG, k)
    if not engrams:
        return ""
    
    rules = []
    for e in engrams:
        try:
            obj = json.loads(e)
            if "abstract_rule" in obj:
                rules.append(obj["abstract_rule"])
        except Exception:
            pass
            
    if not rules:
        return ""
    return "DEEP ENGRAMS (Never forget these rules):\n- " + "\n- ".join(rules)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "consolidate":
        print(consolidate())
    else:
        print("Usage: python3 -m System.swarm_hippocampus consolidate")
