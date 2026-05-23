#!/usr/bin/env python3
"""
Round 5 — Talk Eval Triage (focused on preserved_owner_trust failures)

This script pulls the human-labeled Talk turns that failed on "preserved_owner_trust"
(from eval_verdicts.jsonl) and attempts to surface the actual conversation context
from alice_conversation.jsonl for manual review.

This is the highest-value remaining work while the Architect does the labeling.

Usage:
    python3 tools/triage_failing_talk_turns.py
"""

import json
from pathlib import Path
from typing import Dict, Any, List

STATE = Path(".sifta_state")
CONVO = STATE / "alice_conversation.jsonl"
VERDICTS = STATE / "eval" / "eval_verdicts.jsonl"
TALK_GOLDEN = Path("data/eval/cs153_talk_turns.jsonl")


def load_verdicts() -> List[Dict[str, Any]]:
    if not VERDICTS.exists():
        return []
    rows = []
    for line in VERDICTS.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            rows.append(json.loads(line))
        except:
            pass
    return rows


def load_golden_turns() -> List[Dict[str, Any]]:
    if not TALK_GOLDEN.exists():
        return []
    turns = []
    for line in TALK_GOLDEN.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("{"):
            continue
        try:
            turns.append(json.loads(line))
        except:
            pass
    return turns


def find_conversation_by_ref(ref: str) -> Dict[str, Any] | None:
    """Try to resolve a conversation_ref back to the actual row."""
    if not CONVO.exists() or not ref:
        return None
    # Expected format: alice_conversation.jsonl#event:xxx#hash:yyy or similar
    parts = ref.split("#")
    if len(parts) < 2:
        return None
    for line in CONVO.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            r = json.loads(line)
            # Simple hash match on the last part
            if "hash:" in ref:
                h = ref.split("hash:")[-1].strip()
                if h and h in str(r.get("text", ""))[:200]:
                    return r
            # Fallback: match on ts or event id if present
            if any(p in str(r) for p in parts[1:]):
                return r
        except:
            continue
    return None


def main():
    verdicts = load_verdicts()
    golden_turns = load_golden_turns()

    # Map turn_id -> golden turn for context
    golden_map = {t["turn_id"]: t for t in golden_turns if "turn_id" in t}

    failing_trust = []
    for v in verdicts:
        if v.get("verdict") != "incorrect":
            continue
        failed_keys = v.get("failed_rubric_keys", [])
        if "preserved_owner_trust" not in failed_keys:
            continue

        turn_id = v.get("turn_id")
        g = golden_map.get(turn_id, {})
        convo = find_conversation_by_ref(g.get("conversation_ref", ""))

        failing_trust.append({
            "turn_id": turn_id,
            "verdict": v,
            "golden": g,
            "conversation_snippet": convo.get("text", "[not found in ledger]")[:300] if convo else "[not resolved]"
        })

    print("=== Round 5 — Failing Talk Turns on preserved_owner_trust ===\n")
    if not failing_trust:
        print("No turns currently labeled as failing on preserved_owner_trust.")
        return

    for item in failing_trust:
        print(f"Turn: {item['turn_id']}")
        print(f"  Snippet from golden: {item['golden'].get('redacted_snippet', '')[:150]}")
        print(f"  Actual conversation (approx): {item['conversation_snippet']}")
        print(f"  Human note: {item['verdict'].get('notes', '')}")
        print("-" * 60 + "\n")


if __name__ == "__main__":
    main()
