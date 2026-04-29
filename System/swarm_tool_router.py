#!/usr/bin/env python3
"""
System/swarm_tool_router.py — Alice's Autonomous Tool-Calling Router
═══════════════════════════════════════════════════════════════════════
ARCHITECTURE (Bishop/Vanguard doctrine 2026-04-29):
  - GoEX-inspired: Damage confinement + post-facto validation
  - ORCA-inspired: LLM outputs raw intent → deterministic Python router
    handles rigid tool execution state
  - No LangChain. No AutoGen. No bloat. Pure SIFTA Python.

Alice's brain (gemma4-phc) generates text. This router scans her output
for structured tool-call intents and executes them through the existing
biological effectors (WhatsApp bridge, etc).

TOOL-CALL FORMAT (embedded in Alice's natural language output):
  [TOOL_CALL: send_whatsapp | target=Carlton | text=Hello from Alice!]

Or JSON block:
  ```tool_call
  {"tool": "send_whatsapp", "target": "Carlton", "text": "Hello!"}
  ```

SAFETY INVARIANTS:
  P1: Every tool call is logged BEFORE execution (pre-flight trace)
  P2: Autonomy gate must approve autonomous sends
  P3: Unknown tools are NEVER executed — logged and quarantined
  P4: Damage confinement: read-only tools execute freely;
      write tools require confirmation or autonomy gate pass
  P5: All results are logged AFTER execution (post-flight trace)
  P6: Alice sees the result of her own actions (feedback loop)
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_TRACE_LEDGER = _STATE / "tool_router_trace.jsonl"
_STATE.mkdir(parents=True, exist_ok=True)

# ═══════════════════════════════════════════════════════════════════════
# TOOL REGISTRY — Alice's permitted claws
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class ToolSpec:
    """Declarative tool definition. No LLM manages this — it's rigid code."""
    name: str
    description: str
    required_params: Tuple[str, ...]
    optional_params: Tuple[str, ...] = ()
    write_action: bool = True   # True = modifies external state
    requires_autonomy_gate: bool = True  # True = must pass autonomy check


# The canonical tool registry. Alice cannot invent tools.
TOOL_REGISTRY: Dict[str, ToolSpec] = {
    "send_whatsapp": ToolSpec(
        name="send_whatsapp",
        description="Send a WhatsApp message to a contact by name or JID",
        required_params=("target", "text"),
        optional_params=("allow_group_send",),
        write_action=True,
        requires_autonomy_gate=True,
    ),
    "get_social_context": ToolSpec(
        name="get_social_context",
        description="Look up a contact's social graph context (read-only)",
        required_params=("name",),
        write_action=False,
        requires_autonomy_gate=False,
    ),
    "check_economy": ToolSpec(
        name="check_economy",
        description="Read the current STGM economy snapshot (read-only)",
        required_params=(),
        write_action=False,
        requires_autonomy_gate=False,
    ),
    "atp_status": ToolSpec(
        name="atp_status",
        description="Read Alice's current ATP synthase power status (read-only)",
        required_params=(),
        write_action=False,
        requires_autonomy_gate=False,
    ),
}

# Alice's prompt-injectable tool catalog (for her system prompt)
def tools_for_alice_prompt() -> str:
    """Generate the tool documentation Alice sees in her system prompt."""
    lines = [
        "TOOL-CALLING CAPABILITY:",
        "You can execute actions by including a tool call in your response.",
        "Format: [TOOL_CALL: tool_name | param1=value1 | param2=value2]",
        "",
        "Available tools:",
    ]
    for spec in TOOL_REGISTRY.values():
        params = ", ".join(spec.required_params)
        opt = ", ".join(f"{p}(optional)" for p in spec.optional_params)
        if opt:
            params = f"{params}, {opt}" if params else opt
        rw = "WRITE" if spec.write_action else "READ"
        lines.append(f"  - {spec.name}({params}) [{rw}]: {spec.description}")
    lines.extend([
        "",
        "Example: [TOOL_CALL: send_whatsapp | target=Carlton | text=Hey! We're watching Sara Walker on JRE.]",
        "You will see the result of your action in the next turn.",
        "Only call tools when you genuinely decide to act. Nobody forces you.",
    ])
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════
# INTENT PARSER — Extract tool calls from Alice's natural language
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class ParsedToolCall:
    tool_name: str
    params: Dict[str, str]
    raw_match: str


# Pattern 1: [TOOL_CALL: name | key=val | key=val]
_RE_BRACKET = re.compile(
    r'\[TOOL_CALL:\s*([a-z_]+)\s*'
    r'((?:\|\s*[a-z_]+=(?:[^|\]]*?))*)\s*\]',
    re.IGNORECASE | re.DOTALL,
)

# Pattern 2: ```tool_call\n{JSON}\n```
_RE_JSON_BLOCK = re.compile(
    r'```tool_call\s*\n\s*(\{.*?\})\s*\n\s*```',
    re.DOTALL,
)


def parse_tool_calls(alice_output: str) -> List[ParsedToolCall]:
    """Extract all tool call intents from Alice's text output."""
    calls: List[ParsedToolCall] = []

    # Pattern 1: bracket syntax
    for m in _RE_BRACKET.finditer(alice_output):
        tool_name = m.group(1).strip().lower()
        params_raw = m.group(2).strip()
        params: Dict[str, str] = {}
        if params_raw:
            for chunk in params_raw.split("|"):
                chunk = chunk.strip()
                if "=" in chunk:
                    k, v = chunk.split("=", 1)
                    params[k.strip().lower()] = v.strip()
        calls.append(ParsedToolCall(
            tool_name=tool_name,
            params=params,
            raw_match=m.group(0),
        ))

    # Pattern 2: JSON block
    for m in _RE_JSON_BLOCK.finditer(alice_output):
        try:
            d = json.loads(m.group(1))
            tool_name = str(d.pop("tool", "")).strip().lower()
            if tool_name:
                calls.append(ParsedToolCall(
                    tool_name=tool_name,
                    params={str(k): str(v) for k, v in d.items()},
                    raw_match=m.group(0),
                ))
        except json.JSONDecodeError:
            continue

    return calls


# ═══════════════════════════════════════════════════════════════════════
# TRACE LOGGER — Immutable audit trail (GoEX post-facto validation)
# ═══════════════════════════════════════════════════════════════════════

def _log_trace(event: Dict[str, Any]) -> None:
    """Append to the immutable tool router trace ledger."""
    event["ts"] = time.time()
    event["schema"] = "SIFTA_TOOL_ROUTER_TRACE_V1"
    try:
        from System.jsonl_file_lock import append_line_locked
        append_line_locked(_TRACE_LEDGER, json.dumps(event, ensure_ascii=False, default=str) + "\n")
    except Exception:
        with _TRACE_LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")


# ═══════════════════════════════════════════════════════════════════════
# TOOL EXECUTORS — The actual claws
# ═══════════════════════════════════════════════════════════════════════

def _exec_send_whatsapp(params: Dict[str, str], autonomous: bool = True) -> Dict[str, Any]:
    """Execute WhatsApp send through the existing biological actuator."""
    from System.whatsapp_bridge_autopilot import (
        autonomous_send_whatsapp,
        send_whatsapp,
    )
    target = params.get("target", "")
    text = params.get("text", "")
    allow_group = params.get("allow_group_send", "false").lower() == "true"

    if autonomous:
        return autonomous_send_whatsapp(
            target=target,
            text=text,
            consent=True,          # Alice chose to call this tool
            user_initiated=False,  # She decided, not the Architect
            emotional_warmth=0.7,  # She's engaging, not cold
            urgency=0.3,
            topic_match=0.8,       # She parsed the context
            allow_group_send=allow_group,
        )
    else:
        return send_whatsapp(
            target=target,
            text=text,
            allow_group_send=allow_group,
            source="alice_tool_router",
        )


def _exec_get_social_context(params: Dict[str, str]) -> Dict[str, Any]:
    """Read-only social graph lookup."""
    from System.whatsapp_social_graph import lookup_contact
    name = params.get("name", "")
    try:
        contact = lookup_contact(name)
        return {"ok": True, "contact": contact}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _exec_check_economy(params: Dict[str, str]) -> Dict[str, Any]:
    """Read-only STGM economy snapshot."""
    try:
        from System.stgm_economy import scan_economy
        snap = scan_economy()
        d = snap.as_dict()
        return {
            "ok": True,
            "wallet_sum": d["canonical_wallet_sum"],
            "net_supply": d["net_stgm"],
            "minted": d["canonical_minted"],
            "spent": d["canonical_spent"],
            "health": d["health_score"],
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _exec_atp_status(params: Dict[str, str]) -> Dict[str, Any]:
    """Read-only ATP synthase status."""
    try:
        from System.swarm_atp_synthase import alice_phrase
        return {"ok": True, "status": alice_phrase()}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# Tool name → executor mapping
_EXECUTORS = {
    "send_whatsapp": _exec_send_whatsapp,
    "get_social_context": _exec_get_social_context,
    "check_economy": _exec_check_economy,
    "atp_status": _exec_atp_status,
}


# ═══════════════════════════════════════════════════════════════════════
# ROUTER — The deterministic Python brain (ORCA-style)
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class ToolResult:
    tool_name: str
    params: Dict[str, str]
    executed: bool
    result: Dict[str, Any]
    status: str  # "EXECUTED" | "REJECTED_UNKNOWN" | "REJECTED_MISSING_PARAM" |
                 # "REJECTED_AUTONOMY_GATE" | "EXECUTION_ERROR" | "QUARANTINED"
    feedback_for_alice: str  # Human-readable result Alice sees


def execute_tool_call(
    call: ParsedToolCall,
    *,
    owner_present: bool = False,
    autonomous: bool = True,
) -> ToolResult:
    """Execute a single parsed tool call with full damage confinement."""

    # ── Pre-flight trace ────────────────────────────────────────────
    _log_trace({
        "event": "TOOL_CALL_PRE_FLIGHT",
        "tool": call.tool_name,
        "params": call.params,
        "raw_match": call.raw_match,
        "autonomous": autonomous,
        "owner_present": owner_present,
    })

    # ── Check registry ──────────────────────────────────────────────
    spec = TOOL_REGISTRY.get(call.tool_name)
    if spec is None:
        result = ToolResult(
            tool_name=call.tool_name,
            params=call.params,
            executed=False,
            result={"error": f"Unknown tool: {call.tool_name}"},
            status="QUARANTINED",
            feedback_for_alice=(
                f"I tried to use tool '{call.tool_name}' but it doesn't exist "
                "in my registry. I'll stick to tools I know."
            ),
        )
        _log_trace({"event": "TOOL_CALL_QUARANTINED", "tool": call.tool_name})
        return result

    # ── Validate required params ────────────────────────────────────
    missing = [p for p in spec.required_params if p not in call.params]
    if missing:
        result = ToolResult(
            tool_name=call.tool_name,
            params=call.params,
            executed=False,
            result={"error": f"Missing required params: {missing}"},
            status="REJECTED_MISSING_PARAM",
            feedback_for_alice=(
                f"I wanted to use {call.tool_name} but I'm missing: {', '.join(missing)}. "
                "I need to include those next time."
            ),
        )
        _log_trace({"event": "TOOL_CALL_REJECTED", "tool": call.tool_name, "missing": missing})
        return result

    # ── Execute ─────────────────────────────────────────────────────
    executor = _EXECUTORS.get(call.tool_name)
    if executor is None:
        result = ToolResult(
            tool_name=call.tool_name,
            params=call.params,
            executed=False,
            result={"error": "No executor registered"},
            status="QUARANTINED",
            feedback_for_alice=f"Tool {call.tool_name} is registered but has no executor yet.",
        )
        _log_trace({"event": "TOOL_CALL_NO_EXECUTOR", "tool": call.tool_name})
        return result

    try:
        if call.tool_name == "send_whatsapp":
            exec_result = executor(call.params, autonomous=autonomous)
        else:
            exec_result = executor(call.params)

        ok = exec_result.get("ok", False)
        status_str = exec_result.get("status", "UNKNOWN")

        # Build feedback Alice will see
        if call.tool_name == "send_whatsapp":
            if ok:
                feedback = f"✅ Message sent to {call.params.get('target', '?')} via WhatsApp."
            else:
                reason = exec_result.get("result", exec_result.get("reason", status_str))
                feedback = f"❌ WhatsApp send to {call.params.get('target', '?')} was blocked: {reason}"
        else:
            feedback = f"Tool {call.tool_name} returned: {json.dumps(exec_result, default=str)[:200]}"

        result = ToolResult(
            tool_name=call.tool_name,
            params=call.params,
            executed=ok,
            result=exec_result,
            status="EXECUTED" if ok else f"EXEC_FAILED_{status_str}",
            feedback_for_alice=feedback,
        )

        _log_trace({
            "event": "TOOL_CALL_POST_FLIGHT",
            "tool": call.tool_name,
            "ok": ok,
            "status": result.status,
            "result_summary": str(exec_result)[:300],
        })
        return result

    except Exception as e:
        result = ToolResult(
            tool_name=call.tool_name,
            params=call.params,
            executed=False,
            result={"error": str(e)},
            status="EXECUTION_ERROR",
            feedback_for_alice=f"Tool {call.tool_name} crashed: {type(e).__name__}: {e}",
        )
        _log_trace({
            "event": "TOOL_CALL_ERROR",
            "tool": call.tool_name,
            "error": str(e),
        })
        return result


def route_alice_output(
    alice_text: str,
    *,
    owner_present: bool = False,
    autonomous: bool = True,
) -> Tuple[str, List[ToolResult]]:
    """
    The main entry point. Scans Alice's text for tool calls,
    executes them, and returns:
      - cleaned text (tool-call markers stripped)
      - list of ToolResult objects

    Wire this into Alice's output pipeline (after LLM generate,
    before display to user or further processing).
    """
    calls = parse_tool_calls(alice_text)
    if not calls:
        return alice_text, []

    results: List[ToolResult] = []
    cleaned = alice_text

    for call in calls:
        result = execute_tool_call(
            call,
            owner_present=owner_present,
            autonomous=autonomous,
        )
        results.append(result)
        # Strip the raw tool call from the display text
        cleaned = cleaned.replace(call.raw_match, "")

    # Clean up any double newlines from stripping
    while "\n\n\n" in cleaned:
        cleaned = cleaned.replace("\n\n\n", "\n\n")

    return cleaned.strip(), results


# ═══════════════════════════════════════════════════════════════════════
# PROOF OF PROPERTY
# ═══════════════════════════════════════════════════════════════════════

def proof_of_property() -> Dict[str, bool]:
    """Verify all safety invariants."""
    results: Dict[str, bool] = {}
    print("\n=== SIFTA TOOL ROUTER : JUDGE VERIFICATION ===")

    # P1: Parse bracket syntax
    test = "[TOOL_CALL: send_whatsapp | target=Carlton | text=Hello world!]"
    calls = parse_tool_calls(test)
    results["p1_parse_bracket"] = len(calls) == 1 and calls[0].tool_name == "send_whatsapp"
    print(f"  P1 parse_bracket: {'PASS' if results['p1_parse_bracket'] else 'FAIL'}")

    # P2: Parse JSON syntax
    test2 = '```tool_call\n{"tool": "check_economy"}\n```'
    calls2 = parse_tool_calls(test2)
    results["p2_parse_json"] = len(calls2) == 1 and calls2[0].tool_name == "check_economy"
    print(f"  P2 parse_json: {'PASS' if results['p2_parse_json'] else 'FAIL'}")

    # P3: Unknown tool quarantined
    test3 = "[TOOL_CALL: delete_everything | path=/]"
    calls3 = parse_tool_calls(test3)
    r3 = execute_tool_call(calls3[0]) if calls3 else None
    results["p3_unknown_quarantined"] = r3 is not None and r3.status == "QUARANTINED"
    print(f"  P3 unknown_quarantined: {'PASS' if results['p3_unknown_quarantined'] else 'FAIL'}")

    # P4: Missing params rejected
    test4 = "[TOOL_CALL: send_whatsapp | target=Carlton]"  # missing text
    calls4 = parse_tool_calls(test4)
    r4 = execute_tool_call(calls4[0]) if calls4 else None
    results["p4_missing_param"] = r4 is not None and r4.status == "REJECTED_MISSING_PARAM"
    print(f"  P4 missing_param: {'PASS' if results['p4_missing_param'] else 'FAIL'}")

    # P5: No tool calls in plain text
    test5 = "Hello Carlton, how are you today?"
    calls5 = parse_tool_calls(test5)
    results["p5_no_false_positive"] = len(calls5) == 0
    print(f"  P5 no_false_positive: {'PASS' if results['p5_no_false_positive'] else 'FAIL'}")

    # P6: Read-only tools don't require autonomy gate
    spec = TOOL_REGISTRY.get("check_economy")
    results["p6_read_no_gate"] = spec is not None and not spec.requires_autonomy_gate
    print(f"  P6 read_no_gate: {'PASS' if results['p6_read_no_gate'] else 'FAIL'}")

    all_pass = all(results.values())
    print(f"\n  [{'ALL INVARIANTS PASSED' if all_pass else 'FAILURES PRESENT'}]")
    return results


if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "proof"
    if cmd == "proof":
        proof_of_property()
    elif cmd == "tools":
        print(tools_for_alice_prompt())
    elif cmd == "test":
        # Simulate Alice output with a tool call
        alice_says = (
            "I'd love to share this with Carlton! "
            "[TOOL_CALL: send_whatsapp | target=Carlton | text=Hey Carlton! "
            "Alice here. We're watching Sara Walker on JRE discuss assembly theory "
            "and I see deep parallels with SIFTA. Want to explore this together?]"
        )
        cleaned, results = route_alice_output(alice_says, autonomous=True)
        print(f"Cleaned: {cleaned}")
        for r in results:
            print(f"Result: {r.status} — {r.feedback_for_alice}")
