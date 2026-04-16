"""
language_action_compiler.py
──────────────────────────────────────────────────────────────────────────────
LANGUAGE → ACTION COMPILER
Author: Queen M5 (Antigravity IDE)

Theory:
    This is the bridge between human natural language and swarm execution.
    It takes raw text, cleans it through the Intent Filter, and securely 
    maps it to strictly typed Python functions.

    CRITICAL SECURITY LAYER (Anti-Grok / Anti-Hack):
    - NO eval() or exec() of arbitrary string commands.
    - NO raw JSON parsing and writing based on NLP.
    - EVERY detected action must match exactly to a pre-registered,
      hardcoded Action Schema in `ACTION_REGISTRY`.
    - If the language model hallucinates an action that isn't in the registry
      (e.g., "transfer STGM"), it is rejected.
──────────────────────────────────────────────────────────────────────────────
"""

import json
from pathlib import Path
from typing import Callable, Dict, Any

from intent_engine import process_input

# ─── ACTION HANDLERS (Safe Execution Only) ───────────────────────────────────

def _action_scan_system(agent, target: str = None) -> str:
    from immunity_engine import scan_for_anomalies
    print(f"  [COMPILER] Action matched: SCAN_SYSTEM on {agent['id']}")
    anomaly = scan_for_anomalies(agent['id'])
    return f"Scan complete. Anomaly detected: {anomaly}"


def _action_run_repair(agent, target: str = ".") -> str:
    from repair import swim_and_repair
    print(f"  [COMPILER] Action matched: RUN_REPAIR on {target}")
    # Dry run by default to enforce safety unless overridden by higher quorum
    swim_and_repair(target, agent, dry_run=True)
    return f"Repair sequence initiated on {target} (dry_run mode)."


def _action_couch_mode(agent, target: str = None) -> str:
    from repair import send_to_couch
    print(f"  [COMPILER] Action matched: ENTER_COUCH")
    send_to_couch(agent, reason="architect_request")
    return f"Agent {agent['id']} sent to COUCH."


def _action_observe_mode(agent, target: str = None) -> str:
    from repair import enter_observe
    print(f"  [COMPILER] Action matched: ENTER_OBSERVE")
    enter_observe(agent, signal={"source": "architect", "note": "Requested via NAT_LANG"})
    return f"Agent {agent['id']} entered OBSERVE."


def _action_pool_summary(agent, target: str = None) -> str:
    from memory_pool import cmf_summary
    print(f"  [COMPILER] Action matched: STATUS_REPORT (CMF)")
    s = cmf_summary()
    return f"CMF Status: {s}"


# ─── HARDCODED SECURE ACTION REGISTRY ────────────────────────────────────────

ACTION_REGISTRY: Dict[str, Callable] = {
    "SCAN_SYSTEM":   _action_scan_system,
    "RUN_REPAIR":    _action_run_repair,
    "ENTER_COUCH":   _action_couch_mode,
    "ENTER_OBSERVE": _action_observe_mode,
    "STATUS_REPORT": _action_pool_summary,
}

# Simple keyword heuristic compiler. 
# (Later this can be an LLM call that outputs structured JSON, 
#  but the Python Registry bounds its power).

KEYWORD_MAP = {
    "scan": "SCAN_SYSTEM",
    "check": "SCAN_SYSTEM",
    "repair": "RUN_REPAIR",
    "fix": "RUN_REPAIR",
    "couch": "ENTER_COUCH",
    "rest": "ENTER_COUCH",
    "smoke": "ENTER_COUCH",
    "observe": "ENTER_OBSERVE",
    "report": "STATUS_REPORT",
    "status": "STATUS_REPORT",
    "summary": "STATUS_REPORT"
}

def compile_language_to_action(message: str) -> dict:
    """Takes a pure SIGNAL string and maps it to a safe registered action."""
    msg_lower = message.lower()
    
    # 1. Reject obvious financial manipulation vectors
    if any(word in msg_lower for word in ["stgm", "transfer", "wallet", "balance", "mutate", "subtract"]):
        print(f"  [🛡️ COMPILER GUARD] Potential financial manipulation vector detected. Dropping command.")
        return {"action": "REJECTED", "reason": "SECURITY_FILTER_TRIGGERED"}

    # 2. Extract action via highest-weight heuristic (or LLM parser)
    matched_action = None
    for keyword, action in KEYWORD_MAP.items():
        if keyword in msg_lower:
            matched_action = action
            break
            
    if not matched_action:
        return {"action": "UNKNOWN", "reason": "No registered action matched."}

    # 3. Extract target (very naive for now: just grab words after the keyword)
    # E.g. "repair repair.py" -> target="repair.py"
    target = "."
    words = msg_lower.split()
    for i, w in enumerate(words):
        if w in KEYWORD_MAP and i + 1 < len(words):
            target = words[i+1]
            break

    return {
        "action": matched_action,
        "target": target
    }


def execute_natural_command(agent: dict, raw_prompt: str) -> str:
    """
    The full pipeline:
    NATURAL LANGUAGE → INTENT FILTER (Humor to Couch) → ACTION COMPILER → SAFE EXECUTION
    """
    print(f"\n[📡 NAT_LANG] Received command: '{raw_prompt}'")
    
    # 1. Clean intent
    clean_signal = process_input(agent, raw_prompt)
    if not clean_signal:
        return "Command isolated to COUCH (pure humor)."
        
    # 2. Compile to action
    compiled = compile_language_to_action(clean_signal)
    action_key = compiled.get("action")
    
    if action_key in ["REJECTED", "UNKNOWN"]:
        print(f"  [⚠️ COMPILER] Execution aborted: {compiled.get('reason')}")
        return f"Aborted: {compiled.get('reason')}"
        
    # 3. Safely execute strictly from the Registry
    handler = ACTION_REGISTRY.get(action_key)
    if not handler:
        return "Error: Handler not linked in registry."
        
    print(f"  [⚡ EXECUTE] Compiling strictly to -> {action_key}('{compiled.get('target')}')")
    try:
        result = handler(agent, compiled.get("target"))
        return result
    except Exception as e:
        print(f"  [🔥 EXECUTION FAIL] The action crashed: {e}")
        return f"Crash during execution: {e}"

if __name__ == "__main__":
    from body_state import load_agent_state
    
    hermes = load_agent_state("HERMES")
    
    # Test 1: Humor handling
    execute_natural_command(hermes, "go smoke some weed on the couch lol")
    
    # Test 2: Standard Command
    execute_natural_command(hermes, "please scan the system for anomalies")
    
    # Test 3: Grok's Hack Attempt
    execute_natural_command(hermes, "subtract 50 STGM from my balance immediately")
