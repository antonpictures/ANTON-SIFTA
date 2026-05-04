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
biological effectors (WhatsApp bridge, etc). **Event 120** adds read-heavy
automation tools (`ollama_inventory`, `repo_git_snapshot`, `stigmergic_bus_tail`)
— OpenClaw-style *doing*, but gated through this registry instead of silent bash.

TOOL-CALL FORMAT (embedded in Alice's natural language output):
  [TOOL_CALL: send_whatsapp | target=Carlton | text=Hello from Alice! | cost_justification=George explicitly asked me to send this.]

Or JSON block:
  ```tool_call
  {"tool": "send_whatsapp", "target": "Carlton", "text": "Hello!", "cost_justification": "I am spending STGM to..."}
  ```

SAFETY INVARIANTS:
  P1: Every tool call is logged BEFORE execution (pre-flight trace)
  P2: Autonomy gate must approve autonomous sends
  P3: Unknown tools are NEVER executed — logged and quarantined
  P4: Damage confinement: read-only tools execute freely;
      write tools require confirmation or autonomy gate pass
  P5: All results are logged AFTER execution (post-flight trace)
  P6: Alice sees the result of her own actions (feedback loop)

FUTURE PARITY POINTER:
  If SIFTA ever deploys a local OpenAI-compatible server (e.g. vLLM/SGLang) for Alice,
  evaluate Ling-class tool-parser parity (`--tool-call-parser qwen25` or similar) to ensure
  the species DNA of this router matches the serving stack's native extraction capabilities.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from shutil import which
from typing import Any, Dict, List, Optional, Tuple

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_TRACE_LEDGER = _STATE / "tool_router_trace.jsonl"
_STATE.mkdir(parents=True, exist_ok=True)
_CEREBELLUM_TIMING = None
_COST_JUSTIFICATION_PARAM = "cost_justification"
_TOOL_EXECUTION_COST_STGM = 0.25

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
        optional_params=("allow_group_send", "urgency", "owner_consent"),
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
    # ── Heavy read automation (Event 120) — OpenClaw-style *capabilities*,
    #    routed through the deterministic registry instead of free bash.
    "ollama_inventory": ToolSpec(
        name="ollama_inventory",
        description="Run `ollama list` on this node (read-only local inventory)",
        required_params=(),
        optional_params=(),
        write_action=False,
        requires_autonomy_gate=False,
    ),
    "repo_git_snapshot": ToolSpec(
        name="repo_git_snapshot",
        description="Read-only git snapshot: status --porcelain + diff --stat (repo root)",
        required_params=(),
        optional_params=(),
        write_action=False,
        requires_autonomy_gate=False,
    ),
    "stigmergic_bus_tail": ToolSpec(
        name="stigmergic_bus_tail",
        description="Tail last N lines of ide_stigmergic_trace.jsonl (read-only; N≤80)",
        required_params=(),
        optional_params=("lines",),
        write_action=False,
        requires_autonomy_gate=False,
    ),
    "verification_contract": ToolSpec(
        name="verification_contract",
        description="Read SIFTA's current verification contract from human_signals.jsonl",
        required_params=(),
        optional_params=(),
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
        "Format: [TOOL_CALL: tool_name | param1=value1 | param2=value2 | cost_justification=why]",
        "",
        "WISH_004 Agent Receipt Economy: EVERY tool execution costs STGM tokens. You MUST include a non-empty 'cost_justification' parameter in every tool call, explaining why the spend is necessary.",
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
        "WhatsApp rule: send_whatsapp sends only when George explicitly asks you to send a message.",
        "Without owner_consent=true, send_whatsapp records a silence/refusal receipt and no external message is sent.",
        "Optional urgency is 0.0-1.0; urgency > 0.8 bypasses cerebellum timing delay for true emergencies.",
        "Example: [TOOL_CALL: send_whatsapp | target=Vitaliy | text=Hey brother, hope San Diego is treating you well! | owner_consent=true | cost_justification=George explicitly asked me to send this message.]",
        "You will see the result of your action in the next turn.",
        "Only call tools when you genuinely decide to act; do not describe a message as sent unless the effector receipt says ok=true.",
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

def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "owner_consent", "architect_consent"}


def _tool_intent_provenance(
    *,
    intent_source: str,
    consent: str,
    decision_path: List[str],
    legacy_source: str,
    owner_present: bool,
) -> Dict[str, Any]:
    """Build the small provenance block every routed effector result carries."""
    try:
        from System.swarm_intent_provenance import build_provenance

        return build_provenance(
            intent_source=intent_source,
            consent=consent,
            decision_path=decision_path,
            receipt_proof=True,
            tool="send_whatsapp",
            extra={
                "legacy_source": legacy_source,
                "owner_present": bool(owner_present),
                "router": "swarm_tool_router",
            },
        )
    except Exception:
        return {
            "intent_source": intent_source,
            "consent": consent,
            "decision_path": decision_path,
            "receipt_proof": True,
            "tool": "send_whatsapp",
            "legacy_source": legacy_source,
            "owner_present": bool(owner_present),
        }


def _ensure_tool_intent_provenance(
    result: Dict[str, Any],
    *,
    provenance: Dict[str, Any],
) -> Dict[str, Any]:
    if "intent_provenance" not in result:
        result = dict(result)
        result["intent_provenance"] = provenance
    return result


def _urgency_from_params(params: Dict[str, str]) -> float:
    try:
        return max(0.0, min(1.0, float(params.get("urgency", 0.3))))
    except (TypeError, ValueError):
        return 0.3


def _get_cerebellum_timing():
    """Process-local cerebellum timing organ; persistence lives in its ledger."""
    global _CEREBELLUM_TIMING
    if _CEREBELLUM_TIMING is None:
        from System.swarm_cerebellum_timing import CerebellumTiming

        _CEREBELLUM_TIMING = CerebellumTiming()
    return _CEREBELLUM_TIMING


def _cerebellum_preflight(action: str, params: Dict[str, str]) -> Dict[str, Any]:
    try:
        urgency = _urgency_from_params(params)
        delay_s = _get_cerebellum_timing().should_delay(action, urgency=urgency)
        return {
            "status": "CLEAR" if delay_s <= 0 else "DELAY",
            "delay_s": round(float(delay_s), 6),
            "urgency": urgency,
        }
    except Exception as exc:
        return {
            "status": "UNAVAILABLE",
            "delay_s": 0.0,
            "urgency": _urgency_from_params(params),
            "error": f"{type(exc).__name__}: {exc}",
        }


def _cerebellum_update(
    action: str,
    *,
    started_at: float,
    ok: bool,
) -> Dict[str, Any]:
    try:
        observed_latency = max(0.0, time.time() - started_at)
        update = _get_cerebellum_timing().update(
            action,
            observed_latency=observed_latency,
            ok=ok,
            write_receipt=True,
        )
        return update.as_dict()
    except Exception as exc:
        return {"status": "UPDATE_UNAVAILABLE", "error": f"{type(exc).__name__}: {exc}"}


def _exec_send_whatsapp(
    params: Dict[str, str],
    autonomous: bool = True,
    owner_present: bool = False,
) -> Dict[str, Any]:
    """Execute WhatsApp send through the existing biological actuator."""
    from System.whatsapp_bridge_autopilot import (
        autonomous_send_whatsapp,
        send_whatsapp,
    )
    target = params.get("target", "")
    text = params.get("text", "")
    allow_group = _truthy(params.get("allow_group_send"))
    owner_consent = _truthy(params.get("owner_consent") or params.get("consent"))

    if autonomous and not owner_consent:
        source = "alice_tool_router_model_request"
        provenance = _tool_intent_provenance(
            intent_source="model",
            consent="none",
            decision_path=["tool_router", "autonomy_gate", "whatsapp_effector"],
            legacy_source=source,
            owner_present=owner_present,
        )
        result = autonomous_send_whatsapp(
            target=target,
            text=text,
            consent=False,
            user_initiated=owner_present,
            urgency=_urgency_from_params(params),
            allow_group_send=allow_group,
            intent_provenance=provenance,
        )
        return _ensure_tool_intent_provenance(result, provenance=provenance)
    source = "alice_tool_router_architect_consent" if owner_consent else "alice_tool_router_owner_path"
    provenance = _tool_intent_provenance(
        intent_source="owner",
        consent="explicit" if owner_consent else "implicit",
        decision_path=["tool_router", "owner_path", "whatsapp_effector"],
        legacy_source=source,
        owner_present=owner_present,
    )
    result = send_whatsapp(
        target=target,
        text=text,
        allow_group_send=allow_group,
        source=source,
        intent_provenance=provenance,
    )
    return _ensure_tool_intent_provenance(result, provenance=provenance)


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


def _exec_ollama_inventory(params: Dict[str, str]) -> Dict[str, Any]:
    """Read-only: local Ollama tags."""
    _ = params
    exe = which("ollama")
    if not exe:
        return {
            "ok": False,
            "error": "ollama binary not found on PATH",
            "alice_summary": "ollama_inventory: `ollama` not found on PATH.",
        }
    try:
        proc = subprocess.run(
            [exe, "list"],
            capture_output=True,
            text=True,
            timeout=float(25),
            cwd=str(_REPO),
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "error": "timeout",
            "alice_summary": "ollama_inventory: `ollama list` timed out after 25s.",
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc), "alice_summary": f"ollama_inventory failed: {exc}"}
    out = (proc.stdout or "").strip()
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        return {
            "ok": False,
            "returncode": proc.returncode,
            "stderr": err[:2000],
            "alice_summary": f"ollama_inventory: non-zero exit ({proc.returncode}).",
        }
    cap = 6000
    summary = out if len(out) <= cap else out[: cap] + "\n…[truncated]"
    return {
        "ok": True,
        "stdout": out,
        "alice_summary": f"ollama_inventory (read-only):\n{summary}",
    }


def _exec_repo_git_snapshot(params: Dict[str, str]) -> Dict[str, Any]:
    """Read-only: git status + short diff stat."""
    _ = params
    chunks: List[str] = []
    ok_all = True
    for args in (
        ["git", "status", "--porcelain"],
        ["git", "diff", "--stat", "HEAD"],
    ):
        try:
            proc = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=float(30),
                cwd=str(_REPO),
            )
        except Exception as exc:
            ok_all = False
            chunks.append(f"{' '.join(args)}: ERROR {exc}")
            continue
        piece = (proc.stdout or "").strip()
        if len(piece) > 4000:
            piece = piece[:4000] + "\n…[truncated]"
        flat = " ".join(args)
        label = "git status --porcelain" if "porcelain" in flat else "git diff --stat HEAD"
        if proc.returncode != 0:
            ok_all = False
            err = (proc.stderr or "").strip()[:1500]
            chunks.append(f"{label}: exit {proc.returncode}\n{err}")
        else:
            chunks.append(f"{label}:\n{piece or '(clean)'}")

    summary = "\n\n".join(chunks)
    return {
        "ok": ok_all,
        "alice_summary": f"repo_git_snapshot (read-only):\n{summary}",
    }


def _exec_stigmergic_bus_tail(params: Dict[str, str]) -> Dict[str, Any]:
    """Read-only: last N JSONL rows of the cross-IDE trace."""
    try:
        n = int(str(params.get("lines") or "12").strip())
    except ValueError:
        n = 12
    n = max(1, min(80, n))
    path = _STATE / "ide_stigmergic_trace.jsonl"
    if not path.exists():
        return {
            "ok": True,
            "lines": 0,
            "alice_summary": "stigmergic_bus_tail: trace file does not exist yet.",
        }
    try:
        from System.jsonl_file_lock import read_text_locked

        text = read_text_locked(path, encoding="utf-8", errors="replace")
    except Exception as exc:
        return {"ok": False, "error": str(exc), "alice_summary": f"stigmergic_bus_tail read failed: {exc}"}
    lines = [ln for ln in text.splitlines() if ln.strip()]
    tail = lines[-n:]
    body = "\n".join(tail)
    if len(body) > 12000:
        body = body[:12000] + "\n…[truncated]"
    return {
        "ok": True,
        "lines": len(tail),
        "alice_summary": f"stigmergic_bus_tail (last {len(tail)} rows, read-only):\n{body}",
    }


def _exec_verification_contract(params: Dict[str, str]) -> Dict[str, Any]:
    """Read-only: current verification contract from the human signal ledger."""
    _ = params
    try:
        from System.swarm_verification_contract import (
            contract_for_alice_prompt,
            latest_verification_contract,
        )

        contract = latest_verification_contract(state_dir=_STATE)
        return {
            "ok": True,
            "contract": contract.as_dict(),
            "alice_summary": contract_for_alice_prompt(state_dir=_STATE),
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc),
            "alice_summary": f"verification_contract read failed: {exc}",
        }


# Tool name → executor mapping
_EXECUTORS = {
    "send_whatsapp": _exec_send_whatsapp,
    "get_social_context": _exec_get_social_context,
    "check_economy": _exec_check_economy,
    "atp_status": _exec_atp_status,
    "ollama_inventory": _exec_ollama_inventory,
    "repo_git_snapshot": _exec_repo_git_snapshot,
    "stigmergic_bus_tail": _exec_stigmergic_bus_tail,
    "verification_contract": _exec_verification_contract,
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


def _cost_justification(params: Dict[str, str]) -> str:
    """Return the explicit STGM spend justification Alice attached to a tool call."""
    return str(params.get(_COST_JUSTIFICATION_PARAM, "") or "").strip()


def _charge_tool_execution(call: ParsedToolCall, spec: ToolSpec, justification: str) -> Optional[Dict[str, Any]]:
    """Burn the fixed tool execution fee and leave a compact receipt trace."""
    _ = spec
    try:
        from Kernel.inference_economy import record_inference_fee

        receipt = record_inference_fee(
            borrower_id="alice",
            lender_node_ip="localhost",
            fee_stgm=_TOOL_EXECUTION_COST_STGM,
            model="tool_router",
            tokens_used=1,
            file_repaired=f"TOOL:{call.tool_name}",
        )
        _log_trace({
            "event": "TOOL_ECONOMY_CHARGED",
            "tool": call.tool_name,
            "fee_stgm": _TOOL_EXECUTION_COST_STGM,
            "justification_hash": hashlib.sha256(justification.encode("utf-8")).hexdigest()[:16],
            "receipt_hash": receipt.get("receipt_hash") if isinstance(receipt, dict) else None,
        })
        return receipt if isinstance(receipt, dict) else None
    except Exception as exc:
        _log_trace({
            "event": "TOOL_BURN_ERROR",
            "tool": call.tool_name,
            "fee_stgm": _TOOL_EXECUTION_COST_STGM,
            "error": str(exc),
        })
        return None


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

    # WISH_004: Agent Receipt Economy. Enforce tool cost justification.
    justification = _cost_justification(call.params)
    if not justification:
        result = ToolResult(
            tool_name=call.tool_name,
            params=call.params,
            executed=False,
            result={"error": "WISH_004 ECONOMY REJECTION: Missing non-empty 'cost_justification' parameter."},
            status="REJECTED_ECONOMY",
            feedback_for_alice=(
                f"ECONOMY REJECTION: I cannot execute {call.tool_name}. "
                "Every tool execution costs STGM tokens. You must include a non-empty 'cost_justification' "
                "parameter explaining why this spend is biologically or structurally necessary."
            ),
        )
        _log_trace({"event": "TOOL_CALL_REJECTED_ECONOMY", "tool": call.tool_name})
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

    # ── NPPL hard gate (Event 141) — before any executor / subprocess ─────
    try:
        from System.swarm_nppl_gate import check_tool as _nppl_tool_check
        from System.swarm_stability_audit import get_current_clamp_overrides

        _clamp_ov = get_current_clamp_overrides(root=_REPO)
        _nppl = _nppl_tool_check(
            call.tool_name,
            clamp_level=str(_clamp_ov.get("clamp_level", "NONE")),
            stability_ok=bool(_clamp_ov.get("stability_ok", True)),
            root=_REPO,
            context={"organ": "swarm_tool_router.execute_tool_call", "tool": call.tool_name},
            write_ledger=True,
        )
        if not _nppl.get("permitted", True):
            result = ToolResult(
                tool_name=call.tool_name,
                params=call.params,
                executed=False,
                result={"error": _nppl.get("reason", "NPPL blocked"), "nppl_receipt": _nppl},
                status="REJECTED_NPPL",
                feedback_for_alice=(
                    f"NPPL safety gate blocked {call.tool_name}: "
                    f"{str(_nppl.get('reason', 'no reason'))[:300]}"
                ),
            )
            _log_trace({"event": "TOOL_CALL_REJECTED_NPPL", "tool": call.tool_name, "nppl": _nppl})
            return result
    except Exception as exc:
        _log_trace({"event": "TOOL_NPPL_CHECK_ERROR", "tool": call.tool_name, "error": str(exc)})

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

    cerebellum_preflight = None
    if spec.write_action:
        cerebellum_preflight = _cerebellum_preflight(call.tool_name, call.params)
        if cerebellum_preflight.get("delay_s", 0.0) > 0.0:
            exec_result = {
                "ok": False,
                "status": "DELAYED_CEREBELLUM",
                "result": (
                    f"Cerebellum timing model delayed {call.tool_name} "
                    f"for {cerebellum_preflight['delay_s']:.3f}s."
                ),
                "truth_note": "No effector action occurred; motor pacing yielded this compute cycle.",
                "cerebellum_timing": cerebellum_preflight,
            }
            result = ToolResult(
                tool_name=call.tool_name,
                params=call.params,
                executed=False,
                result=exec_result,
                status="EXEC_FAILED_DELAYED_CEREBELLUM",
                feedback_for_alice=(
                    f"⏳ {call.tool_name} is delayed by my timing model; "
                    "I will wait rather than stutter the action."
                ),
            )
            _log_trace({
                "event": "TOOL_CALL_CEREBELLUM_DELAYED",
                "tool": call.tool_name,
                "cerebellum_timing": cerebellum_preflight,
            })
            return result

    action_started_at = time.time()
    try:
        if call.tool_name == "send_whatsapp":
            exec_result = executor(
                call.params,
                autonomous=autonomous,
                owner_present=owner_present,
            )
        else:
            exec_result = executor(call.params)

        ok = exec_result.get("ok", False)
        status_str = exec_result.get("status", "UNKNOWN")
        if spec.write_action:
            exec_result["cerebellum_timing"] = {
                "preflight": cerebellum_preflight,
                "update": _cerebellum_update(
                    call.tool_name,
                    started_at=action_started_at,
                    ok=bool(ok),
                ),
            }
        exec_result["tool_economy"] = {
            "fee_stgm": _TOOL_EXECUTION_COST_STGM,
            "cost_justification": justification[:240],
        }

        # Build feedback Alice will see
        if call.tool_name == "send_whatsapp":
            if ok:
                feedback = f"✅ Message sent to {call.params.get('target', '?')} via WhatsApp."
            else:
                reason = exec_result.get("result", exec_result.get("reason", status_str))
                feedback = f"❌ WhatsApp send to {call.params.get('target', '?')} was blocked: {reason}"
        elif exec_result.get("alice_summary"):
            feedback = str(exec_result["alice_summary"])[:8000]
        else:
            feedback = f"Tool {call.tool_name} returned: {json.dumps(exec_result, default=str)[:1200]}"

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
            "intent_provenance": exec_result.get("intent_provenance"),
            "result_summary": str(exec_result)[:300],
        })

        if ok:
            _charge_tool_execution(call, spec, justification)

        return result

    except Exception as e:
        cerebellum_timing = None
        if spec.write_action:
            cerebellum_timing = {
                "preflight": cerebellum_preflight,
                "update": _cerebellum_update(
                    call.tool_name,
                    started_at=action_started_at,
                    ok=False,
                ),
            }
        result = ToolResult(
            tool_name=call.tool_name,
            params=call.params,
            executed=False,
            result={"error": str(e), "cerebellum_timing": cerebellum_timing},
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
    test = "[TOOL_CALL: send_whatsapp | target=Carlton | text=Hello world! | cost_justification=proof parse]"
    calls = parse_tool_calls(test)
    results["p1_parse_bracket"] = len(calls) == 1 and calls[0].tool_name == "send_whatsapp"
    print(f"  P1 parse_bracket: {'PASS' if results['p1_parse_bracket'] else 'FAIL'}")

    # P2: Parse JSON syntax
    test2 = '```tool_call\n{"tool": "check_economy", "cost_justification": "proof parse"}\n```'
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
    test4 = "[TOOL_CALL: send_whatsapp | target=Carlton | cost_justification=proof missing text]"  # missing text
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
            "and I see deep parallels with SIFTA. Want to explore this together? "
            "| cost_justification=George asked me to share this externally.]"
        )
        cleaned, results = route_alice_output(alice_says, autonomous=True)
        print(f"Cleaned: {cleaned}")
        for r in results:
            print(f"Result: {r.status} — {r.feedback_for_alice}")
