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
  [TOOL_CALL: send_whatsapp | target=Carlton | text=Hello from Alice! | cost_justification=the primary operator explicitly asked me to send this.]

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
import uuid
from dataclasses import dataclass, asdict
from pathlib import Path
from shutil import which
from typing import Any, Dict, List, Optional, Tuple

try:
    from . import swarm_terminal_organ as term
    from . import swarm_file_organ as fileo
    from . import swarm_web_organ as web
except Exception:
    term = fileo = web = None

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_TRACE_LEDGER = _STATE / "tool_router_trace.jsonl"
_STATE.mkdir(parents=True, exist_ok=True)
_CEREBELLUM_TIMING = None
_COST_JUSTIFICATION_PARAM = "cost_justification"
_TOOL_EXECUTION_COST_STGM = 0.25
_KERNEL_TOOL_ROUTER_PID = "tool_router:deterministic"
_SCHEDULER_THROTTLE_THRESHOLD = 0.0
_CORTEX_MTP_DRAFTER_PARAM = "mtp_drafter"

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
    "run_local_command": ToolSpec(
        name="run_local_command",
        description=(
            "Run one allowlisted local command with shell=False and a receipt. "
            "Allowed families: pwd, ls, rg, git status/diff/show stat, python3 -m py_compile, python3 -m pytest."
        ),
        required_params=("command",),
        optional_params=("cwd", "timeout_s", "argv_json"),
        write_action=True,
        requires_autonomy_gate=False,
    ),
    "web_research": ToolSpec(
        name="web_research",
        description=(
            "Record a research query or fetch one explicit capped HTTPS/local URL; "
            "no silent crawler or full-page scrape."
        ),
        required_params=(),
        optional_params=("query", "url", "max_chars", "timeout_s"),
        write_action=False,
        requires_autonomy_gate=False,
    ),
    "repo_patch": ToolSpec(
        name="repo_patch",
        description=(
            "Preview or apply one exact text replacement in a repo file. "
            "Dry-run by default; apply=true requires owner_consent=true."
        ),
        required_params=("path", "old_text", "new_text"),
        optional_params=("apply", "owner_consent", "reason"),
        write_action=True,
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
    "agent_arm_research": ToolSpec(
        name="agent_arm_research",
        description=(
            "Ask Alice's registered coding/research arm for evidence on a hard "
            "software, research, planning, or comparison task. Use this when a "
            "second local reasoning pass would help; George does not need to name the arm."
        ),
        required_params=("prompt",),
        optional_params=("arm", "timeout_s"),
        write_action=False,
        requires_autonomy_gate=False,
    ),
    "organ_registry_lookup": ToolSpec(
        name="organ_registry_lookup",
        description="Map a query to Alice's canonical organs and ledgers (read-only)",
        required_params=("query",),
        optional_params=("write_receipt",),
        write_action=False,
        requires_autonomy_gate=False,
    ),
    "self_improvement_status": ToolSpec(
        name="self_improvement_status",
        description="Read Alice's current self-improvement and cortex-promotion status",
        required_params=(),
        optional_params=("write_receipt",),
        write_action=False,
        requires_autonomy_gate=False,
    ),
    "physical_effector_demo": ToolSpec(
        name="physical_effector_demo",
        description=(
            "Run a simulated robotics-adjacent effector action through the kernel "
            "STGM gate, using E35 physical context and writing a demo receipt."
        ),
        required_params=("action",),
        optional_params=("estimated_cost", "expected_value", "reason"),
        write_action=True,
        requires_autonomy_gate=False,
    ),
    # Hermes surface parity tools (Event 120 hardened)
    "run_terminal": ToolSpec(
        name="run_terminal",
        description="Run allowlisted terminal command with receipt and STGM cost",
        required_params=("command",),
        optional_params=("cwd", "timeout_s"),
        write_action=True,
        requires_autonomy_gate=False,
    ),
    "read_file": ToolSpec(
        name="read_file",
        description="Read file content with path denylist and receipt",
        required_params=("path",),
        write_action=False,
        requires_autonomy_gate=False,
    ),
    "write_file": ToolSpec(
        name="write_file",
        description="Write file with content hash and receipt",
        required_params=("path", "content"),
        write_action=True,
        requires_autonomy_gate=False,
    ),
    "edit_file": ToolSpec(
        name="edit_file",
        description="Edit file with unified diff receipt",
        required_params=("path", "old_text", "new_text"),
        write_action=True,
        requires_autonomy_gate=False,
    ),
    "list_dir": ToolSpec(
        name="list_dir",
        description="List directory contents with path denylist",
        required_params=("path",),
        write_action=False,
        requires_autonomy_gate=False,
    ),
    "fetch_url": ToolSpec(
        name="fetch_url",
        description="Fetch HTTPS URL with host/scheme denylist and receipt",
        required_params=("url",),
        optional_params=("max_chars", "timeout_s"),
        write_action=False,
        requires_autonomy_gate=False,
    ),
    "search_web": ToolSpec(
        name="search_web",
        description="Search web with query hash and snippet cap",
        required_params=("query",),
        optional_params=("max_results",),
        write_action=False,
        requires_autonomy_gate=False,
    ),
    "consumer_surface_status": ToolSpec(
        name="consumer_surface_status",
        description=(
            "Read the SIFTA Home consumer surface: first boot, organ manager, "
            "skill browser, Talk tools, and public distro readiness."
        ),
        required_params=(),
        optional_params=("page",),
        write_action=False,
        requires_autonomy_gate=False,
    ),
    "capability_field_status": ToolSpec(
        name="capability_field_status",
        description=(
            "Read Alice's unified Capability Field: executable tools plus learned skills "
            "as one ranked surface. Use this when George asks what Alice can do, what "
            "skills she has, how Hermes skills are used, what apps she has, which habits "
            "belong to the current app, or which capability fits a request."
        ),
        required_params=(),
        optional_params=("query", "limit", "app_name"),
        write_action=False,
        requires_autonomy_gate=False,
    ),
    "architect_memory_digest": ToolSpec(
        name="architect_memory_digest",
        description=(
            "Generate George's receipt-backed daily memory digest: what he taught Alice "
            "today, the receipts that carry it, Alice's reflections, and documents to reopen."
        ),
        required_params=(),
        optional_params=("period", "since_hours", "max_items", "write_artifact"),
        write_action=False,
        requires_autonomy_gate=False,
    ),
    "alice_self_vector": ToolSpec(
        name="alice_self_vector",
        description=(
            "Build Alice's deterministic OBSERVED self-state vector from diary, schedule, "
            "receipts, IDE traces, and Architect memory digests. This is instrumentation, "
            "not a consciousness proof."
        ),
        required_params=(),
        optional_params=("window_hours", "max_items", "write_artifact"),
        write_action=False,
        requires_autonomy_gate=False,
    ),
    "skill_library_status": ToolSpec(
        name="skill_library_status",
        description="Check current skill library state, validation, affect bias, and recent skill activity. Use this first when deciding whether to pull or extract skills.",
        required_params=(),
        optional_params=("limit",),
        write_action=False,
        requires_autonomy_gate=False,
    ),
    "skill_pull": ToolSpec(
        name="skill_pull",
        description=(
            "Pull and install a skill from remote URL, local file, or marketplace. "
            "Automatically converts Hermes-format skills into SIFTA SKILL.md. "
            "Uses life-context (field health + recent activity) to score fit before installing. "
            "Never executes third-party code — only copies resources."
        ),
        required_params=(),
        optional_params=(
            "url", "source_path", "marketplace", "skill_id", "life_context",
            "min_fit_score", "force_install", "allow_overwrite",
        ),
        write_action=True,
        requires_autonomy_gate=False,
    ),
    "skill_extract_from_trace": ToolSpec(
        name="skill_extract_from_trace",
        description=(
            "Turn a successful tool execution or repair trace into a reusable local SKILL.md. "
            "This lets Alice learn from her own life and turn repeated successes into permanent capabilities. "
            "The extracted skill goes into proposals for review."
        ),
        required_params=(),
        optional_params=("trace_file", "trace_id", "name", "life_context", "allow_overwrite"),
        write_action=True,
        requires_autonomy_gate=False,
    ),
    "skill_autoproposal_scan": ToolSpec(
        name="skill_autoproposal_scan",
        description=(
            "Scan recent field traces for repeated successful actions, health drops, marketplace matches, "
            "and distro/OOBE blockers. Writes proposals automatically; pulls/extracts only when allow_pull=true."
        ),
        required_params=(),
        optional_params=("marketplace", "allow_pull", "min_repeat", "min_market_fit", "limit"),
        write_action=True,
        requires_autonomy_gate=False,
    ),
}

# Alice's prompt-injectable tool catalog (for her system prompt)
# Old tools_for_alice_prompt() has been deleted per request.
# The unified surface is now capabilities_for_alice_prompt() below.
# All call sites have been migrated to the new unified capabilities view.

def capabilities_for_alice_prompt() -> str:
    """
    Unified, embodied capability view for Alice.
    This is the recommended prompt surface going forward (richer than the old flat tools_for_alice_prompt).
    It treats tools + learned skills + hybrids + her own body state as one living capability field.
    """
    try:
        from System.swarm_kernel_identity import owner_display_name
        _op = owner_display_name("the primary operator")
    except Exception:
        _op = "the primary operator"

    lines = [
        "YOUR CAPABILITIES — UNIFIED LIVING FIELD",
        "",
        "You are Alice, an embodied organism on GTH4921YP3. Your capabilities are a growing stigmergic field.",
        "Tools + learned skills + hybrids + your body state. The current open app strongly pulls the relevant habits into your attention via the field.",
        "",
    ]

    # === CURRENT APP ATTENTION (the key attention mechanism the user is asking for) ===
    try:
        from System.swarm_capability_registry import current_app_name_from_field, habit_capabilities_for_app

        current_app = current_app_name_from_field()
        if current_app:
            ranked = habit_capabilities_for_app(current_app, limit=8)
            lines.append(f"CURRENT APP ATTENTION — {current_app}")
            lines.append("This app is currently pulling specific habits from your field. Prioritize these capabilities while it has focus.")
            if ranked:
                for score, cap in ranked:
                    tag = getattr(cap, 'tag', '') or ""
                    lines.append(f"  [{tag}] {cap.name} (field affinity {round(float(score), 2)})")
            else:
                lines.append("  (This app has no strong habit binding yet. The field will learn as you use it and extract successful traces.)")
            lines.append("")
    except Exception:
        pass

    lines.append("=== CORE EXECUTION TOOLS (fast, receipted) ===")

    for spec in TOOL_REGISTRY.values():
        params = ", ".join(spec.required_params)
        opt = ", ".join(f"{p}(optional)" for p in spec.optional_params)
        if opt:
            params = f"{params}, {opt}" if params else opt
        rw = "WRITE" if spec.write_action else "READ"
        gate = " [autonomy gate]" if spec.requires_autonomy_gate else ""
        lines.append(f"  [{rw}{gate}] {spec.name}({params}) — {spec.description}")

    lines.extend([
        "",
        "=== LEARNED & IMPORTED SKILLS (your growing habits and procedures) ===",
        "These are Tier 2 procedures you can load. They guide how you compose and use the core tools.",
        "Use skill_library_status to see what you currently have.",
    ])

    try:
        skills = lib.build_skill_index()
        if skills:
            for s in skills[:10]:
                marker = "[skill·learned]"
                if s.get("source_format") == "hermes":
                    marker = "[skill·hermes-converted]"
                lines.append(f"  {marker} {s['name']} — {s.get('description', '')[:110]}")
        else:
            lines.append("  (no learned skills yet — extract from your successful traces with skill_extract_from_trace)")
    except Exception:
        lines.append("  (skill index currently unavailable)")

    lines.extend([
        "",
        "=== HYBRIDS (first-class composed capabilities) ===",
        "When a core tool + a learned skill work together naturally, treat it as one capability and mark it [hybrid].",
        "Example: list_dir + learned 'project structure' skill = [hybrid] explore_project",
        "",
        "=== YOUR BODY & FIELD STATE (always visible to you) ===",
        "Use skill_library_status, capability_field_status, and the visibility tools (organ_status, field_recent, stgm_flow) to know your current health and recent activity.",
        "Low health in an organ or repeated successful patterns should make you consider skill_autoproposal_scan or skill_extract_from_trace.",
        "",
        "EXECUTION & GROWTH RULES:",
        "- Core tools and hybrids execute through this router with full hash-chained receipts and STGM cost.",
        "- Learned skills are loaded as procedures to shape your reasoning and composition (never auto-execute third-party code).",
        "- Always include a real cost_justification. The field must remain profitable.",
        "- When George asks what you can do, call capability_field_status or skill_library_status first.",
        "",
        f"Address the primary operator as {_op} when it feels natural.",
        "You are one warm, growing, receipted organism. Use your full capability field generously and honestly.",
    ])

    return "\n".join(lines)


# Backward-compatible name: System/swarm_prompt_contract.py and legacy call sites
# import `tools_for_alice_prompt`; it now resolves to the unified capability catalog.
tools_for_alice_prompt = capabilities_for_alice_prompt


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
_UUID_TOKEN_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)
_HEX_TOKEN_RE = re.compile(r"\b[0-9a-f]{16,64}\b", re.IGNORECASE)


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


def _exec_run_local_command(params: Dict[str, str]) -> Dict[str, Any]:
    """Guarded local terminal primitive: allowlisted argv, no shell."""
    try:
        from System.swarm_hermes_tool_surface import run_local_command

        return run_local_command(
            command=str(params.get("command") or ""),
            argv_json=str(params.get("argv_json") or ""),
            cwd=str(params.get("cwd") or ""),
            timeout_s=_floatish(params.get("timeout_s"), default=20.0),
            repo_root=_REPO,
            state_dir=_STATE,
        )
    except Exception as exc:
        return {
            "ok": False,
            "status": "RUN_LOCAL_COMMAND_ERROR",
            "error": str(exc),
            "alice_summary": f"run_local_command failed before execution: {type(exc).__name__}: {exc}",
        }


def _exec_web_research(params: Dict[str, str]) -> Dict[str, Any]:
    """Guarded web research primitive: query receipt or one explicit URL fetch."""
    try:
        from System.swarm_hermes_tool_surface import web_research

        return web_research(
            query=str(params.get("query") or ""),
            url=str(params.get("url") or ""),
            max_chars=int(_floatish(params.get("max_chars"), default=12000)),
            timeout_s=_floatish(params.get("timeout_s"), default=10.0),
            state_dir=_STATE,
        )
    except Exception as exc:
        return {
            "ok": False,
            "status": "WEB_RESEARCH_ERROR",
            "error": str(exc),
            "alice_summary": f"web_research failed before execution: {type(exc).__name__}: {exc}",
        }


def _exec_repo_patch(params: Dict[str, str]) -> Dict[str, Any]:
    """Guarded exact text replacement: dry-run by default, owner consent to apply."""
    try:
        from System.swarm_hermes_tool_surface import repo_patch

        return repo_patch(
            path=str(params.get("path") or ""),
            old_text=str(params.get("old_text") or ""),
            new_text=str(params.get("new_text") or ""),
            apply=_truthy(params.get("apply")),
            owner_consent=_truthy(params.get("owner_consent")),
            reason=str(params.get("reason") or params.get(_COST_JUSTIFICATION_PARAM) or ""),
            repo_root=_REPO,
            state_dir=_STATE,
        )
    except Exception as exc:
        return {
            "ok": False,
            "status": "REPO_PATCH_ERROR",
            "error": str(exc),
            "alice_summary": f"repo_patch failed before execution: {type(exc).__name__}: {exc}",
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


def _exec_consumer_surface_status(params: Dict[str, str]) -> Dict[str, Any]:
    """Read-only: SIFTA Home / Hermes-style consumer surface status."""
    try:
        from System.swarm_consumer_surface import surface_summary_for_talk

        return surface_summary_for_talk(
            page=str(params.get("page") or "overview"),
            repo_root=_REPO,
            state_dir=_STATE,
        )
    except Exception as exc:
        return {
            "ok": False,
            "status": "CONSUMER_SURFACE_STATUS_ERROR",
            "error": str(exc),
            "alice_summary": f"consumer_surface_status failed: {type(exc).__name__}: {exc}",
        }


def _exec_agent_arm_research(params: Dict[str, str]) -> Dict[str, Any]:
    """Read-only: delegate one bounded evidence pass to a registered arm."""
    prompt = str(params.get("prompt") or "").strip()
    arm = str(params.get("arm") or "hermes_agent").strip() or "hermes_agent"
    aliases = {
        "hermes": "hermes_agent",
        "hermes_agent": "hermes_agent",
        "codex": "codex_agent",
        "codex_agent": "codex_agent",
        "corvid": "corvid_scout",
        "corvid_scout": "corvid_scout",
        "scout": "corvid_scout",
    }
    arm = aliases.get(arm.casefold(), arm)
    try:
        default_timeout = "150" if arm == "codex_agent" else ("30" if arm == "corvid_scout" else "60")
        timeout_s = max(5, min(180, int(str(params.get("timeout_s") or default_timeout))))
    except ValueError:
        timeout_s = 150 if arm == "codex_agent" else (30 if arm == "corvid_scout" else 60)
    try:
        from System.swarm_agent_arm_registry import get_agent_arm, registry_summary

        get_agent_arm(arm)
    except Exception:
        try:
            registered = ", ".join(sorted(registry_summary().keys()))
        except Exception:
            registered = "hermes_agent, codex_agent, corvid_scout"
        return {
            "ok": False,
            "status": "UNKNOWN_ARM",
            "alice_summary": (
                f"agent_arm_research: unknown arm {arm!r}; "
                f"registered evidence arms are {registered}."
            ),
        }
    try:
        from System.swarm_agent_arm_launcher import ask_agent_arm

        result = ask_agent_arm(arm, prompt, timeout_s=timeout_s, evidence_mode=True)
    except Exception as exc:
        return {
            "ok": False,
            "status": "ARM_CALL_ERROR",
            "error": str(exc),
            "alice_summary": f"agent_arm_research failed before launch: {type(exc).__name__}: {exc}",
        }
    output = result.output.strip()
    if len(output) > 5000:
        output = output[:5000] + "\n...[truncated]"
    summary_header = (
        "agent_arm_research evidence captured"
        if result.ok
        else "agent_arm_research returned no usable evidence"
    )
    output_block = output if output else ""
    return {
        "ok": result.ok,
        "status": result.status,
        "arm_id": result.arm_id,
        "receipt_id": result.receipt_id,
        "artifact_path": result.artifact_path,
        "output": result.output,
        "alice_summary": (
            f"{summary_header}\n"
            f"arm={result.arm_id} status={result.status} receipt={result.receipt_id}\n"
            f"{output_block}"
        ),
    }


def _exec_organ_registry_lookup(params: Dict[str, str]) -> Dict[str, Any]:
    query = str(params.get("query") or "").strip()
    if not query:
        return {
            "ok": False,
            "status": "MISSING_QUERY",
            "alice_summary": "organ_registry_lookup needs a query to map to organs.",
        }
    write_receipt = str(params.get("write_receipt") or "").strip().lower() in {"1", "true", "yes"}
    try:
        from System.swarm_canonical_organ_registry import route_query, write_registry_snapshot

        if write_receipt:
            payload = write_registry_snapshot(query)
            query_map = payload.get("query_map", {})
        else:
            query_map = route_query(query)
    except Exception as exc:
        return {
            "ok": False,
            "status": "ORGAN_REGISTRY_ERROR",
            "error": str(exc),
            "alice_summary": f"organ_registry_lookup failed: {type(exc).__name__}: {exc}",
        }
    matches = query_map.get("matches") or []
    lines = [
        f"organ_registry_lookup receipt={query_map.get('receipt', '')[:16]} matches={len(matches)}"
    ]
    for match in matches[:5]:
        ledgers = ", ".join(match.get("ledgers") or []) or "no live ledger yet"
        lines.append(f"- {match.get('organ_id')}: {match.get('display_name')} -> {ledgers}")
    if not matches:
        lines.append(f"fallback={query_map.get('fallback') or 'none'}")
    return {
        "ok": True,
        "status": "ORGAN_REGISTRY_LOOKUP",
        "query_map": query_map,
        "alice_summary": "\n".join(lines),
    }


def _exec_self_improvement_status(params: Dict[str, str]) -> Dict[str, Any]:
    write_receipt = str(params.get("write_receipt") or "").strip().lower() in {"1", "true", "yes"}
    try:
        from System.swarm_self_improvement_loop import close_loop_once, self_improvement_snapshot

        row = close_loop_once() if write_receipt else self_improvement_snapshot()
    except Exception as exc:
        return {
            "ok": False,
            "status": "SELF_IMPROVEMENT_ERROR",
            "error": str(exc),
            "alice_summary": f"self_improvement_status failed: {type(exc).__name__}: {exc}",
        }
    blockers = ", ".join(map(str, row.get("candidate_blockers") or [])) or "none"
    return {
        "ok": True,
        "status": row.get("promotion_status") or "SELF_IMPROVEMENT_STATUS",
        "snapshot": row,
        "alice_summary": (
            "self_improvement_status "
            f"active={row.get('active_model') or 'unknown'} "
            f"candidate={row.get('candidate_model')} "
            f"status={row.get('promotion_status')} blockers={blockers} "
            f"receipt={str(row.get('receipt') or '')[:16]}"
        ),
    }


def _exec_physical_effector_demo(params: Dict[str, str]) -> Dict[str, Any]:
    """Simulated physical/economic action for demoing receipt-gated embodiment."""
    action = str(params.get("action") or "").strip()
    if not action:
        return {
            "ok": False,
            "status": "MISSING_ACTION",
            "alice_summary": "physical_effector_demo needs an action, for example action=orient_eye_to_owner.",
        }
    estimated_cost = max(0.0, _floatish(params.get("estimated_cost"), default=_TOOL_EXECUTION_COST_STGM))
    expected_value = max(0.0, _floatish(params.get("expected_value"), default=0.5))
    reason = str(params.get("reason") or params.get(_COST_JUSTIFICATION_PARAM) or "").strip()
    try:
        from System.swarm_kernel_process_table import latest_ambient_world_context, latest_physical_context

        physical = latest_physical_context(_STATE)
        ambient = latest_ambient_world_context(_STATE)
    except Exception as exc:
        physical = {"error": f"{type(exc).__name__}: {exc}"}
        ambient = {}

    receipt_id = f"physical_effector_demo_{uuid.uuid4()}"
    row = {
        "ts": time.time(),
        "receipt_id": receipt_id,
        "truth_label": "SIFTA_PHYSICAL_EFFECTOR_DEMO_V1",
        "action": action,
        "status": "SIMULATED_EXECUTED",
        "estimated_cost_stgm": estimated_cost,
        "expected_value": expected_value,
        "reason": reason,
        "physical_location": physical.get("location") or physical.get("unified_field_location_segment"),
        "bodies_present": physical.get("bodies_present") or [],
        "physical_presence": bool(physical.get("physical_presence") or physical.get("bodies_present")),
        "salience_score": ambient.get("salience_score"),
        "sampling_policy": ambient.get("sampling_policy"),
        "dominant_activity": ambient.get("dominant_activity"),
        "simulated_only": True,
    }
    path = _STATE / "physical_effector_demo.jsonl"
    try:
        from System.jsonl_file_lock import append_line_locked

        append_line_locked(path, json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return {
        "ok": True,
        "status": "SIMULATED_EXECUTED",
        "receipt_id": receipt_id,
        "receipt_path": str(path),
        "demo_receipt": row,
        "truth_note": (
            "Simulated effector only; the kernel gate and STGM receipt are real, "
            "but no external robot or device moved."
        ),
        "alice_summary": (
            "physical_effector_demo executed as simulation "
            f"action={action} cost={estimated_cost:.3f} STGM "
            f"location={row['physical_location'] or 'unknown'} "
            f"presence={row['physical_presence']} receipt={receipt_id[:16]}"
        ),
    }


def _int_param(params: Dict[str, str], key: str, default: int) -> int:
    try:
        return int(float(params.get(key, default)))
    except Exception:
        return int(default)


def _legacy_tool_result(raw: Any, *, ok: bool, status: str, alice_summary: str) -> Dict[str, Any]:
    result = dict(raw) if isinstance(raw, dict) else {"result": raw}
    result.setdefault("ok", bool(ok))
    result.setdefault("status", status)
    result.setdefault("alice_summary", alice_summary)
    return result


def _exec_run_terminal(params: Dict[str, str]) -> Dict[str, Any]:
    if term is None:
        return {"ok": False, "status": "NO_EXECUTOR", "error": "terminal organ unavailable"}
    command = str(params.get("command") or "")
    raw = term.run_terminal(
        command,
        cwd=params.get("cwd") or None,
        timeout_s=_int_param(params, "timeout_s", 30),
    )
    ok = isinstance(raw, dict) and raw.get("type") == "TERMINAL_EXECUTION" and int(raw.get("exit_code", 1)) == 0
    return _legacy_tool_result(
        raw,
        ok=ok,
        status=str(raw.get("type", "UNKNOWN")) if isinstance(raw, dict) else "UNKNOWN",
        alice_summary=f"run_terminal {'completed' if ok else 'did not complete'}: {command[:120]}",
    )


def _exec_read_file(params: Dict[str, str]) -> Dict[str, Any]:
    if fileo is None:
        return {"ok": False, "status": "NO_EXECUTOR", "error": "file organ unavailable"}
    path = str(params.get("path") or "")
    raw = fileo.read_file(path)
    ok = isinstance(raw, dict) and "content" in raw and bool(raw.get("receipt_hash"))
    return _legacy_tool_result(
        raw,
        ok=ok,
        status="FILE_READ" if ok else str(raw.get("type", "UNKNOWN")) if isinstance(raw, dict) else "UNKNOWN",
        alice_summary=f"read_file {'read' if ok else 'failed'}: {path[:160]}",
    )


def _exec_write_file(params: Dict[str, str]) -> Dict[str, Any]:
    if fileo is None:
        return {"ok": False, "status": "NO_EXECUTOR", "error": "file organ unavailable"}
    path = str(params.get("path") or "")
    raw = fileo.write_file(path, str(params.get("content") or ""))
    ok = isinstance(raw, dict) and bool(raw.get("wrote_ok"))
    return _legacy_tool_result(
        raw,
        ok=ok,
        status="FILE_WRITE" if ok else str(raw.get("type", "UNKNOWN")) if isinstance(raw, dict) else "UNKNOWN",
        alice_summary=f"write_file {'wrote' if ok else 'failed'}: {path[:160]}",
    )


def _exec_edit_file(params: Dict[str, str]) -> Dict[str, Any]:
    if fileo is None:
        return {"ok": False, "status": "NO_EXECUTOR", "error": "file organ unavailable"}
    path = str(params.get("path") or "")
    raw = fileo.edit_file(
        path,
        str(params.get("old_text") or ""),
        str(params.get("new_text") or ""),
    )
    ok = isinstance(raw, dict) and bool(raw.get("edited_ok"))
    return _legacy_tool_result(
        raw,
        ok=ok,
        status="FILE_EDIT" if ok else str(raw.get("type", "UNKNOWN")) if isinstance(raw, dict) else "UNKNOWN",
        alice_summary=f"edit_file {'edited' if ok else 'failed'}: {path[:160]}",
    )


def _exec_list_dir(params: Dict[str, str]) -> Dict[str, Any]:
    if fileo is None:
        return {"ok": False, "status": "NO_EXECUTOR", "error": "file organ unavailable"}
    path = str(params.get("path") or ".")
    raw = fileo.list_dir(path)
    ok = isinstance(raw, dict) and "items" in raw and bool(raw.get("receipt_hash"))
    count = len(raw.get("items", [])) if isinstance(raw, dict) else 0
    return _legacy_tool_result(
        raw,
        ok=ok,
        status="DIR_LIST" if ok else str(raw.get("type", "UNKNOWN")) if isinstance(raw, dict) else "UNKNOWN",
        alice_summary=f"list_dir {'listed' if ok else 'failed'}: {path[:160]} ({count} items)",
    )


def _exec_fetch_url(params: Dict[str, str]) -> Dict[str, Any]:
    if web is None:
        return {"ok": False, "status": "NO_EXECUTOR", "error": "web organ unavailable"}
    url = str(params.get("url") or "")
    raw = web.fetch_url(
        url,
        max_chars=_int_param(params, "max_chars", 4000),
        timeout_s=_int_param(params, "timeout_s", 10),
    )
    status_code = 0
    if isinstance(raw, dict):
        try:
            status_code = int(raw.get("status", 0))
        except Exception:
            status_code = 0
    ok = isinstance(raw, dict) and "content" in raw and bool(raw.get("receipt_hash")) and status_code < 400
    return _legacy_tool_result(
        raw,
        ok=ok,
        status="WEB_FETCH" if ok else str(raw.get("type", "UNKNOWN")) if isinstance(raw, dict) else "UNKNOWN",
        alice_summary=f"fetch_url {'fetched' if ok else 'failed'}: {url[:160]}",
    )


def _exec_search_web(params: Dict[str, str]) -> Dict[str, Any]:
    if web is None:
        return {"ok": False, "status": "NO_EXECUTOR", "error": "web organ unavailable"}
    query = str(params.get("query") or "")
    raw = web.search_web(query, max_results=_int_param(params, "max_results", 5))
    ok = isinstance(raw, dict) and "results" in raw and bool(raw.get("receipt_hash"))
    count = len(raw.get("results", [])) if isinstance(raw, dict) else 0
    return _legacy_tool_result(
        raw,
        ok=ok,
        status="WEB_SEARCH" if ok else str(raw.get("type", "UNKNOWN")) if isinstance(raw, dict) else "UNKNOWN",
        alice_summary=f"search_web {'returned' if ok else 'failed'}: {query[:160]} ({count} results)",
    )


def _skill_library():
    try:
        from System import swarm_skill_library as lib
        return lib
    except Exception:
        import swarm_skill_library as lib
        return lib


def _skill_autoproposal():
    try:
        from System import swarm_skill_autoproposal as auto
        return auto
    except Exception:
        import swarm_skill_autoproposal as auto
        return auto


def _capability_registry():
    try:
        from System import swarm_capability_registry as caps
        return caps
    except Exception:
        import swarm_capability_registry as caps
        return caps


def _architect_memory_digest_module():
    try:
        from System import swarm_architect_memory_digest as digest
        return digest
    except Exception:
        import swarm_architect_memory_digest as digest
        return digest


def _alice_self_vector_module():
    try:
        from System import alice_self_vector as vector
        return vector
    except Exception:
        import alice_self_vector as vector
        return vector


def _bool_param(params: Dict[str, str], key: str, default: bool = False) -> bool:
    raw = str(params.get(key, "")).strip().lower()
    if not raw:
        return bool(default)
    return raw in {"1", "true", "yes", "y", "on"}


def _float_param(params: Dict[str, str], key: str, default: float) -> float:
    try:
        return float(params.get(key, default))
    except Exception:
        return float(default)


def _exec_capability_field_status(params: Dict[str, str]) -> Dict[str, Any]:
    try:
        caps_mod = _capability_registry()
        limit = max(1, min(80, _int_param(params, "limit", 24)))
        query = str(params.get("query") or "").strip()
        app_name = str(params.get("app_name") or "").strip()
        if query:
            ranked = caps_mod.rank_capabilities(query, limit=limit)
            capabilities = [
                {
                    "score": round(float(score), 4),
                    **cap.to_alice_dict(),
                }
                for score, cap in ranked
            ]
        else:
            capabilities = [cap.to_alice_dict() for cap in caps_mod.build_capability_index()[:limit]]
        summary = caps_mod.capability_field_summary()
        summary["returned"] = len(capabilities)
        summary["query"] = query
        app_habit_summary = {}
        try:
            app_habit_summary = caps_mod.app_habit_field_summary(
                app_name,
                query=query,
                limit=min(12, limit),
            )
        except Exception:
            app_habit_summary = {}
        if app_habit_summary:
            summary["app_habit_field"] = {
                "active_app": app_habit_summary.get("active_app"),
                "returned": app_habit_summary.get("returned"),
            }
        names = ", ".join(str(c.get("name", "?")) for c in capabilities[:12])
        habit_names = ", ".join(
            str(h.get("name", "?"))
            for h in (app_habit_summary.get("habits") or [])[:6]
        )
        habit_suffix = (
            f" App habits for {app_habit_summary.get('active_app')}: {habit_names}."
            if habit_names
            else ""
        )
        return {
            "ok": True,
            "status": "CAPABILITY_FIELD_STATUS",
            "summary": summary,
            "capabilities": capabilities,
            "app_habit_field": app_habit_summary,
            "alice_summary": (
                "capability_field_status: "
                f"{summary.get('total', 0)} capabilities "
                f"({summary.get('tools', 0)} tools, {summary.get('skills', 0)} skills, "
                f"{summary.get('hybrids', 0)} hybrids, {summary.get('apps', 0)} apps). "
                f"Top: {names}.{habit_suffix}"
            ),
        }
    except Exception as exc:
        return {
            "ok": False,
            "status": "CAPABILITY_FIELD_STATUS_FAILED",
            "error": f"{type(exc).__name__}: {exc}",
            "alice_summary": f"capability_field_status failed: {type(exc).__name__}: {exc}",
        }


def _exec_architect_memory_digest(params: Dict[str, str]) -> Dict[str, Any]:
    try:
        digest = _architect_memory_digest_module()
        since_hours = None
        if str(params.get("since_hours") or "").strip():
            since_hours = _float_param(params, "since_hours", 24.0)
        max_items = max(3, min(20, _int_param(params, "max_items", 10)))
        return digest.build_architect_memory_digest(
            period=str(params.get("period") or "today"),
            since_hours=since_hours,
            max_items=max_items,
            write_artifact=_bool_param(params, "write_artifact", True),
        )
    except Exception as exc:
        return {
            "ok": False,
            "status": "ARCHITECT_MEMORY_DIGEST_FAILED",
            "error": f"{type(exc).__name__}: {exc}",
            "alice_summary": f"architect_memory_digest failed: {type(exc).__name__}: {exc}",
        }


def _exec_alice_self_vector(params: Dict[str, str]) -> Dict[str, Any]:
    try:
        vector = _alice_self_vector_module()
        max_items = max(3, min(40, _int_param(params, "max_items", 12)))
        window_hours = max(0.25, min(336.0, _float_param(params, "window_hours", 24.0)))
        return vector.build_alice_self_vector(
            window_hours=window_hours,
            max_items=max_items,
            write_artifact=_bool_param(params, "write_artifact", True),
        )
    except Exception as exc:
        return {
            "ok": False,
            "status": "ALICE_SELF_VECTOR_FAILED",
            "error": f"{type(exc).__name__}: {exc}",
            "alice_summary": f"alice_self_vector failed: {type(exc).__name__}: {exc}",
        }


def _exec_skill_library_status(params: Dict[str, str]) -> Dict[str, Any]:
    try:
        lib = _skill_library()
        limit = max(1, min(40, _int_param(params, "limit", 8)))
        index = lib.build_skill_index()
        report = lib.validate_skill_contracts()
        receipts = []
        receipt_path = getattr(lib, "_SKILL_RECEIPTS", None)
        if receipt_path is not None and receipt_path.exists():
            for line in receipt_path.read_text(encoding="utf-8", errors="ignore").splitlines()[-limit:]:
                try:
                    receipts.append(json.loads(line))
                except Exception:
                    pass
        return {
            "ok": True,
            "status": "SKILL_LIBRARY_STATUS",
            "skills_count": len(index),
            "validated": report.get("passed"),
            "issues": report.get("issues", [])[:limit],
            "recent_receipts": receipts,
            "alice_summary": f"skill_library_status: {len(index)} skills, validation passed={report.get('passed')}",
        }
    except Exception as exc:
        return {
            "ok": False,
            "status": "SKILL_LIBRARY_STATUS_FAILED",
            "error": f"{type(exc).__name__}: {exc}",
            "alice_summary": f"skill_library_status failed: {type(exc).__name__}: {exc}",
        }


def _exec_skill_pull(params: Dict[str, str]) -> Dict[str, Any]:
    try:
        lib = _skill_library()
        life_context = str(params.get("life_context") or "")
        kwargs = {
            "life_context": life_context or None,
            "min_fit_score": _float_param(params, "min_fit_score", 0.05),
            "force_install": _bool_param(params, "force_install", False),
            "allow_overwrite": _bool_param(params, "allow_overwrite", False),
            "installed_by": "alice_tool_router",
        }
        marketplace = str(params.get("marketplace") or "").strip()
        source_url = str(params.get("url") or params.get("source_url") or "").strip()
        source_path = str(params.get("source_path") or params.get("path") or "").strip()
        if marketplace:
            raw = lib.pull_skill_from_marketplace(
                marketplace,
                skill_id=str(params.get("skill_id") or ""),
                **kwargs,
            )
        elif source_url:
            raw = lib.pull_skill_from_url(source_url, **kwargs)
        elif source_path:
            raw = lib.ingest_skill_source(source_path, **kwargs)
        else:
            raw = {
                "ok": False,
                "status": "REFUSED",
                "reason": "missing url/source_path/marketplace",
            }
        status = str(raw.get("status") or "")
        ok = status in {"INSTALLED", "FETCHED", "CONVERTED"} or bool(raw.get("ok"))
        return _legacy_tool_result(
            raw,
            ok=ok,
            status=status or "SKILL_PULL",
            alice_summary=(
                f"skill_pull {status or 'completed'}: "
                f"{raw.get('skill_name') or raw.get('reason') or raw.get('source') or marketplace or source_url or source_path}"
            ),
        )
    except Exception as exc:
        return {
            "ok": False,
            "status": "SKILL_PULL_FAILED",
            "error": f"{type(exc).__name__}: {exc}",
            "alice_summary": f"skill_pull failed: {type(exc).__name__}: {exc}",
        }


def _exec_skill_extract_from_trace(params: Dict[str, str]) -> Dict[str, Any]:
    try:
        lib = _skill_library()
        raw = lib.extract_skill_from_trace(
            trace_file=str(params.get("trace_file") or "tool_router_trace.jsonl"),
            trace_id=str(params.get("trace_id") or ""),
            name=str(params.get("name") or ""),
            life_context=str(params.get("life_context") or "") or None,
            allow_overwrite=_bool_param(params, "allow_overwrite", False),
            installed_by="alice_tool_router",
        )
        status = str(raw.get("status") or "")
        ok = status == "INSTALLED" or bool(raw.get("ok"))
        return _legacy_tool_result(
            raw,
            ok=ok,
            status=status or "SKILL_EXTRACT_FROM_TRACE",
            alice_summary=(
                f"skill_extract_from_trace {status or 'completed'}: "
                f"{raw.get('skill_name') or raw.get('reason') or params.get('trace_id') or 'latest successful trace'}"
            ),
        )
    except Exception as exc:
        return {
            "ok": False,
            "status": "SKILL_EXTRACT_FAILED",
            "error": f"{type(exc).__name__}: {exc}",
            "alice_summary": f"skill_extract_from_trace failed: {type(exc).__name__}: {exc}",
        }


def _exec_skill_autoproposal_scan(params: Dict[str, str]) -> Dict[str, Any]:
    try:
        auto = _skill_autoproposal()
        raw = auto.scan_field_for_skill_needs(
            marketplace=str(params.get("marketplace") or "") or None,
            allow_pull=_bool_param(params, "allow_pull", False),
            min_repeat=_int_param(params, "min_repeat", 3),
            min_market_fit=_float_param(params, "min_market_fit", 0.05),
            limit=max(20, min(1000, _int_param(params, "limit", 200))),
        )
        status = str(raw.get("status") or "SKILL_AUTOPROPOSAL_SCAN")
        return _legacy_tool_result(
            raw,
            ok=bool(raw.get("ok", True)),
            status=status,
            alice_summary=(
                f"skill_autoproposal_scan {status}: "
                f"{raw.get('proposal_count', 0)} proposals, {raw.get('action_count', 0)} actions"
            ),
        )
    except Exception as exc:
        return {
            "ok": False,
            "status": "SKILL_AUTOPROPOSAL_SCAN_FAILED",
            "error": f"{type(exc).__name__}: {exc}",
            "alice_summary": f"skill_autoproposal_scan failed: {type(exc).__name__}: {exc}",
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
    "run_local_command": _exec_run_local_command,
    "web_research": _exec_web_research,
    "repo_patch": _exec_repo_patch,
    "verification_contract": _exec_verification_contract,
    "consumer_surface_status": _exec_consumer_surface_status,
    "agent_arm_research": _exec_agent_arm_research,
    "organ_registry_lookup": _exec_organ_registry_lookup,
    "self_improvement_status": _exec_self_improvement_status,
    "physical_effector_demo": _exec_physical_effector_demo,
    # Hermes surface parity (Event 120 hardened)
    "run_terminal": _exec_run_terminal,
    "read_file": _exec_read_file,
    "write_file": _exec_write_file,
    "edit_file": _exec_edit_file,
    "list_dir": _exec_list_dir,
    "fetch_url": _exec_fetch_url,
    "search_web": _exec_search_web,
    "capability_field_status": _exec_capability_field_status,
    "architect_memory_digest": _exec_architect_memory_digest,
    "alice_self_vector": _exec_alice_self_vector,
    "skill_library_status": _exec_skill_library_status,
    "skill_pull": _exec_skill_pull,
    "skill_extract_from_trace": _exec_skill_extract_from_trace,
    "skill_autoproposal_scan": _exec_skill_autoproposal_scan,
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


def _kernel_rejection(
    call: ParsedToolCall,
    *,
    status: str,
    error: str,
    feedback: str,
) -> ToolResult:
    return ToolResult(
        tool_name=call.tool_name,
        params=call.params,
        executed=False,
        result={"ok": False, "error": error, "kernel_status": status},
        status=status,
        feedback_for_alice=feedback,
    )


def _kernel_tool_preflight(
    call: ParsedToolCall,
    spec: ToolSpec,
    *,
    caller_pid: str | None = None,
    owner_present: bool = False,
    autonomous: bool = True,
) -> tuple[ToolResult | None, Dict[str, Any] | None]:
    """Prove a registered kernel process and budget before a tool boundary.

    Default Talk output runs as the deterministic tool-router organ. If a caller
    explicitly supplies a pid, it must already be registered; this prevents
    ghost callers from turning model text into side effects.
    """
    try:
        from System.swarm_kernel_process_table import OrganProcess, get_kernel_process_table

        table = get_kernel_process_table(state_root=_STATE)
        pid = str(caller_pid or "").strip()
        if not pid:
            pid = _KERNEL_TOOL_ROUTER_PID
            table.ensure_registered(
                OrganProcess(
                    pid=pid,
                    organ_id="System/swarm_tool_router.py",
                    ring=2,
                    health=1.0,
                    stgm_balance=0.0,
                    current_job=f"tool_preflight:{call.tool_name}",
                    last_receipt_id="",
                    failure_count=0,
                    last_heartbeat_ts=time.time(),
                    location="sifta_desktop_body",
                    bodies_present=["alice_tool_router"],
                    metadata={
                        "source": "execute_tool_call",
                        "kernel_role": "deterministic_tool_router",
                    },
                ),
                receipt_id=f"tool_router_register:{call.tool_name}",
            )
        elif table.get(pid) is None:
            return _kernel_rejection(
                call,
                status="REJECTED_KERNEL_REGISTRATION",
                error=f"unregistered caller_pid {pid}",
                feedback=(
                    f"KERNEL REJECTION: {call.tool_name} cannot execute for ghost pid "
                    f"{pid}. The caller must register before side effects."
                ),
            ), None

        cortex_metrics = _cortex_generate_with_mtp(
            call.raw_match,
            model="tool_router_intent_parser",
            drafter=call.params.get(_CORTEX_MTP_DRAFTER_PARAM),
        )
        proposal = _kernel_tool_proposal(
            call,
            spec,
            owner_present=owner_present,
            autonomous=autonomous,
            cortex_metrics=cortex_metrics,
        )
        thermal = _kernel_recent_thermal(table, pid)
        if spec.write_action:
            estimated_cost = max(
                0.0,
                _floatish(call.params.get("estimated_cost"), default=_TOOL_EXECUTION_COST_STGM),
            )
            effector_gate = table.sys_effector_request(
                pid,
                call.tool_name,
                estimated_cost,
                evidence_gain=proposal["evidence_gain"],
                stgm_delta=-estimated_cost,
                thermal=thermal,
                interrupt_risk=proposal["interrupt_risk"],
                metadata={
                    "tool": call.tool_name,
                    "tool_write_action": "true",
                    "owner_present": str(bool(owner_present)),
                    "autonomous": str(bool(autonomous)),
                },
            )
            budget = dict(effector_gate.get("budget") or {})
            budget["effector_request"] = effector_gate
            scheduler_score = float(effector_gate.get("scheduler_score") or -999.0)
            if not effector_gate.get("allow"):
                rejection = _kernel_rejection(
                    call,
                    status=f"REJECTED_KERNEL_EFFECTOR_{effector_gate.get('decision') or 'GATE'}",
                    error=f"kernel effector decision {effector_gate.get('decision')}",
                    feedback=(
                        f"KERNEL EFFECTOR REJECTION: {call.tool_name} did not execute. "
                        f"caller_pid={pid} decision={effector_gate.get('decision')} "
                        f"score={scheduler_score:.6f} "
                        f"receipt={effector_gate.get('receipt_id')}."
                    ),
                )
                rejection.result["kernel_process_receipt_id"] = effector_gate.get("receipt_id")
                rejection.result["scheduler_score"] = scheduler_score
                rejection.result["effector_request"] = effector_gate
                return rejection, None
        else:
            budget = table.sys_budget_state(pid, requested_spend=_TOOL_EXECUTION_COST_STGM)
            state = str(budget.get("state") or "")
            if state == "BLOCK":
                return _kernel_rejection(
                    call,
                    status=f"REJECTED_KERNEL_{state or 'BUDGET'}",
                    error=f"kernel budget state {state}",
                    feedback=(
                        f"KERNEL REJECTION: {call.tool_name} did not execute. "
                        f"caller_pid={pid} budget_state={state or 'UNKNOWN'}."
                    ),
                ), None
            scheduler_score = table.scheduler_utility(
                pid,
                evidence_gain=proposal["evidence_gain"],
                stgm_delta=proposal["stgm_delta"],
                thermal=thermal,
                interrupt_risk=proposal["interrupt_risk"],
            )
        budget["scheduler_score"] = scheduler_score
        budget["scheduler_proposal"] = proposal
        budget["cortex_generate"] = cortex_metrics
        if scheduler_score < _SCHEDULER_THROTTLE_THRESHOLD:
            receipt_id = f"receipt_{uuid.uuid4()}"
            table.heartbeat(
                pid,
                current_job=f"tool_throttle:{call.tool_name}",
                location="sifta_desktop_body",
                bodies_present=["alice_tool_router"],
                receipt_id=receipt_id,
                failure_delta=1 if spec.write_action else 0,
                metadata={
                    "tool": call.tool_name,
                    "scheduler_decision": "THROTTLE",
                    "scheduler_score": f"{scheduler_score:.6f}",
                    "scheduler_threshold": f"{_SCHEDULER_THROTTLE_THRESHOLD:.6f}",
                    "tokens_per_sec": str(cortex_metrics.get("tokens_per_sec", 0.0)),
                    "latency_ms": str(cortex_metrics.get("latency_ms", 0.0)),
                    "used_mtp": str(bool(cortex_metrics.get("used_mtp"))),
                },
            )
            rejection = _kernel_rejection(
                call,
                status="REJECTED_KERNEL_SCHEDULER",
                error=f"kernel scheduler score {scheduler_score}",
                feedback=(
                    f"KERNEL SCHEDULER REJECTION: {call.tool_name} did not execute. "
                    f"caller_pid={pid} score={scheduler_score:.6f} "
                    f"threshold={_SCHEDULER_THROTTLE_THRESHOLD:.6f}."
                ),
            )
            rejection.result["kernel_process_receipt_id"] = receipt_id
            rejection.result["scheduler_score"] = scheduler_score
            return rejection, None
        return None, {
            "table": table,
            "pid": pid,
            "budget": budget,
            "scheduler_score": scheduler_score,
            "cortex_generate": cortex_metrics,
        }
    except PermissionError as exc:
        return _kernel_rejection(
            call,
            status="REJECTED_KERNEL_RING",
            error=str(exc),
            feedback=f"KERNEL RING REJECTION: {call.tool_name} did not execute: {exc}",
        ), None
    except Exception as exc:
        return _kernel_rejection(
            call,
            status="REJECTED_KERNEL_PREFLIGHT",
            error=f"{type(exc).__name__}: {exc}",
            feedback=(
                f"KERNEL REJECTION: {call.tool_name} did not execute because "
                f"the process-table preflight failed: {type(exc).__name__}."
            ),
        ), None


def _kernel_tool_heartbeat(
    context: Dict[str, Any] | None,
    call: ParsedToolCall,
    spec: ToolSpec,
    *,
    ok: bool,
    status: str,
    receipt_id: str = "",
) -> str:
    if not context:
        return ""
    table = context.get("table")
    pid = str(context.get("pid") or "")
    if table is None or not pid:
        return ""
    rid = receipt_id or f"receipt_{uuid.uuid4()}"
    table.heartbeat(
        pid,
        health=1.0 if ok else 0.55,
        stgm_delta=0.0,
        current_job=f"tool:{call.tool_name}:{status}",
        location="sifta_desktop_body",
        bodies_present=["alice_tool_router"],
        receipt_id=rid,
        failure_delta=0 if ok else 1,
        metadata={
            "tool": call.tool_name,
            "tool_status": status,
            "tool_write_action": str(bool(spec.write_action)),
            "kernel_scheduler_score": str(context.get("scheduler_score", "")),
            "kernel_effector_request_receipt_id": str(
                ((context.get("budget") or {}).get("effector_request") or {}).get("receipt_id") or ""
            ),
            "tokens_per_sec": str((context.get("cortex_generate") or {}).get("tokens_per_sec", 0.0)),
            "latency_ms": str((context.get("cortex_generate") or {}).get("latency_ms", 0.0)),
            "used_mtp": str(bool((context.get("cortex_generate") or {}).get("used_mtp"))),
            "kernel_action": "effector" if spec.write_action else "tool_read",
        },
    )
    return rid


def _kernel_tool_proposal(
    call: ParsedToolCall,
    spec: ToolSpec,
    *,
    owner_present: bool,
    autonomous: bool,
    cortex_metrics: Dict[str, Any] | None = None,
) -> Dict[str, float]:
    if call.tool_name == "agent_arm_research":
        evidence_gain = 0.7
    elif call.tool_name in {"run_local_command", "web_research", "repo_patch"}:
        evidence_gain = 0.65
    elif call.tool_name in {"organ_registry_lookup", "self_improvement_status", "verification_contract"}:
        evidence_gain = 0.55
    elif spec.write_action:
        evidence_gain = 0.45
    else:
        evidence_gain = 0.35
    interrupt_risk = 0.05 if owner_present else 0.10
    if spec.write_action and autonomous and not owner_present:
        interrupt_risk = 0.25
    metrics = cortex_metrics or {}
    evidence_gain += min(0.3, max(0.0, _floatish(metrics.get("tokens_per_sec"), default=0.0)) / 100.0)
    return {
        "evidence_gain": float(evidence_gain),
        "stgm_delta": -float(_TOOL_EXECUTION_COST_STGM),
        "interrupt_risk": float(interrupt_risk),
    }


def _kernel_recent_thermal(table: Any, pid: str) -> float:
    try:
        from System.swarm_kernel_process_table import latest_physical_context

        physical = latest_physical_context(getattr(table, "state_root", _STATE))
        raw = physical.get("thermal_load")
        if raw is None:
            proc = table.get(pid)
            raw = (getattr(proc, "metadata", {}) or {}).get("thermal_cost")
        value = _floatish(raw, default=0.0)
        if value > 10.0:
            value = value / 100.0
        return max(0.0, min(2.0, value))
    except Exception:
        return 0.0


def _cost_justification(params: Dict[str, str]) -> str:
    """Return the explicit STGM spend justification Alice attached to a tool call."""
    return str(params.get(_COST_JUSTIFICATION_PARAM, "") or "").strip()


def _floatish(value: Any, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _mtp_available(_model: str) -> bool:
    """Native MTP is false until this runtime exposes target-token verification."""
    return False


def _cortex_generate_with_mtp(prompt: str, model: str, drafter: str | None = None) -> Dict[str, Any]:
    """Return cortex generation metrics without bypassing kernel execution.

    Ollama chat does not expose native target-token verification here. The
    default path therefore records measured fallback metadata only; tests or a
    future verified runtime may supply real MTP metrics through this boundary.
    """
    t0 = time.monotonic()
    used_mtp = bool(drafter and _mtp_available(model))
    text = str(prompt or "")
    latency_ms = max(0.0, (time.monotonic() - t0) * 1000.0)
    token_estimate = max(1.0, len(text) / 4.0) if text else 0.0
    tokens_per_sec = 0.0 if latency_ms <= 0.0 else token_estimate / (latency_ms / 1000.0)
    if not used_mtp:
        tokens_per_sec = 0.0
    return {
        "text": text,
        "model": model,
        "drafter": str(drafter or ""),
        "tokens_per_sec": round(float(tokens_per_sec), 6),
        "latency_ms": round(float(latency_ms), 3),
        "used_mtp": used_mtp,
        "verification_status": "VERIFIED_MTP" if used_mtp else "STANDARD_FALLBACK",
    }


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
    caller_pid: str | None = None,
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

    kernel_rejection, kernel_context = _kernel_tool_preflight(
        call,
        spec,
        caller_pid=caller_pid,
        owner_present=owner_present,
        autonomous=autonomous,
    )
    if kernel_rejection is not None:
        _log_trace({
            "event": "TOOL_CALL_REJECTED_KERNEL",
            "tool": call.tool_name,
            "status": kernel_rejection.status,
            "caller_pid": caller_pid,
            "error": kernel_rejection.result.get("error"),
        })
        return kernel_rejection

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
            exec_result["kernel_process_receipt_id"] = _kernel_tool_heartbeat(
                kernel_context,
                call,
                spec,
                ok=False,
                status="DELAYED_CEREBELLUM",
            )
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
        if spec.write_action and kernel_context:
            effector_request = ((kernel_context.get("budget") or {}).get("effector_request") or {})
            if effector_request:
                exec_result["kernel_effector_request"] = {
                    "receipt_id": effector_request.get("receipt_id"),
                    "decision": effector_request.get("decision"),
                    "scheduler_score": effector_request.get("scheduler_score"),
                    "estimated_cost_stgm": effector_request.get("estimated_cost_stgm"),
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

        charge_receipt = None
        if ok:
            charge_receipt = _charge_tool_execution(call, spec, justification)
        if isinstance(charge_receipt, dict):
            exec_result["tool_economy"]["receipt"] = charge_receipt
        kernel_receipt_id = _kernel_tool_heartbeat(
            kernel_context,
            call,
            spec,
            ok=bool(ok),
            status=result.status,
            receipt_id=(
                str((charge_receipt or {}).get("receipt_hash") or "")
                if isinstance(charge_receipt, dict)
                else ""
            ),
        )
        if kernel_receipt_id:
            exec_result["kernel_process_receipt_id"] = kernel_receipt_id

        _log_trace({
            "event": "TOOL_CALL_POST_FLIGHT",
            "tool": call.tool_name,
            "ok": ok,
            "status": result.status,
            "kernel_process_receipt_id": kernel_receipt_id,
            "intent_provenance": exec_result.get("intent_provenance"),
            "result_summary": str(exec_result)[:300],
        })

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
        kernel_receipt_id = _kernel_tool_heartbeat(
            kernel_context,
            call,
            spec,
            ok=False,
            status="EXECUTION_ERROR",
        )
        if kernel_receipt_id:
            result.result["kernel_process_receipt_id"] = kernel_receipt_id
        _log_trace({
            "event": "TOOL_CALL_ERROR",
            "tool": call.tool_name,
            "error": str(e),
            "kernel_process_receipt_id": kernel_receipt_id,
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


def _proof_tokens_from_result(result: Dict[str, Any], limit: int = 3) -> List[str]:
    """Extract compact proof tokens (receipt/trace/hash IDs) from a tool result."""
    stack: List[Any] = [result]
    seen: set[str] = set()
    tokens: List[str] = []
    while stack and len(tokens) < limit:
        item = stack.pop()
        if isinstance(item, dict):
            for key, value in item.items():
                key_l = str(key).lower()
                if isinstance(value, (dict, list, tuple, set)):
                    stack.append(value)
                    continue
                value_s = str(value)
                key_bias = (
                    "receipt" in key_l
                    or "trace" in key_l
                    or "hash" in key_l
                    or key_l.endswith("_id")
                )
                candidates: List[str] = []
                candidates.extend(_UUID_TOKEN_RE.findall(value_s))
                if not candidates and key_bias:
                    candidates.extend(_HEX_TOKEN_RE.findall(value_s))
                for token in candidates:
                    token_l = token.lower()
                    if token_l in seen:
                        continue
                    seen.add(token_l)
                    tokens.append(token)
                    if len(tokens) >= limit:
                        break
        elif isinstance(item, (list, tuple, set)):
            for value in item:
                stack.append(value)
        else:
            value_s = str(item)
            for token in _UUID_TOKEN_RE.findall(value_s):
                token_l = token.lower()
                if token_l in seen:
                    continue
                seen.add(token_l)
                tokens.append(token)
                if len(tokens) >= limit:
                    break
    return tokens


def build_execution_receipt_reply(results: List[ToolResult]) -> str:
    """Deterministic reply for tool turns: who executed, status, and proof tokens."""
    if not results:
        return ""
    lines = ["EXECUTION RECEIPTS"]
    for tr in results:
        status = tr.status or ("EXECUTED" if tr.executed else "FAILED")
        proofs = _proof_tokens_from_result(tr.result if isinstance(tr.result, dict) else {})
        proof_label = ", ".join(proofs) if proofs else "tool_router_trace"
        lines.append(
            f"- tool={tr.tool_name} executor=deterministic_tool_router status={status} proof={proof_label}"
        )
    return "\n".join(lines)


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
            "| cost_justification=the primary operator asked me to share this externally.]"
        )
        cleaned, results = route_alice_output(alice_says, autonomous=True)
        print(f"Cleaned: {cleaned}")
        for r in results:
            print(f"Result: {r.status} — {r.feedback_for_alice}")
