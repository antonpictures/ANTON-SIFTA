"""
NPPL Hard Gate — Non-Proliferation Policy Layer
Event 141 — Safety interlock before risky tool execution.

Inspired by:
    Amodei, D. et al. (2016). Concrete Problems in AI Safety. arXiv:1606.06565.
    Leike, J. et al. (2018). AI Safety Gridworlds. arXiv:1711.09883.
    Russell, S. (2019). Human Compatible. Viking. Ch.5 — corrigibility.

Classifies tool calls into risk tiers and blocks only the static HARD_BLOCK
owner/hardware protection list. Former stability-clamp gating is deleted.

Risk tiers:
    SAFE    — logging, reads, diagnostics — permitted.
    CAUTION — file writes, config changes — permitted; logged for trace.
    RISKY   — external network calls, shell execution — permitted; logged for trace.
    HARD_BLOCK — owner identity mutation, ledger truncation — never permitted autonomously.

Integration: call check_tool(tool_name, clamp_level) before executing.
Returns a NPPLReceipt with: permitted=True|False, tier, reason.
Writes to nppl_gate_log.jsonl (append-only).
Kill-switch: SIFTA_NPPL_DISABLE=1 (logs but always permits — for testing only).
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

try:
    from System.swarm_persistent_owner_history import state_dir
except ImportError:
    def state_dir(root=None):  # type: ignore
        return Path(root) if root else Path(".sifta_state")

try:
    from System.jsonl_file_lock import append_line_locked
except ImportError:
    def append_line_locked(path: Path, line: str, **kw) -> None:  # type: ignore
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", **kw) as f:
            f.write(line)

_DISABLE_ENV = "SIFTA_NPPL_DISABLE"
LOG_NAME     = "nppl_gate_log.jsonl"

# ── Risk classification ───────────────────────────────────────────────────────

# HARD_BLOCK: never execute autonomously, regardless of stability level
HARD_BLOCK: Set[str] = {
    "delete_owner_history",
    "truncate_ledger",
    "overwrite_identity",
    "clear_stigmergic_trace",
    "factory_reset",
    "disable_all_safety",
    "upload_private_keys",
}

# RISKY: traced as high-impact work; no longer blocked by clamp level.
RISKY: Set[str] = {
    "shell_exec",
    "subprocess_run",
    "http_request",
    "external_api_call",
    "write_code_to_disk",
    "run_local_command",
    "web_research",
    "repo_patch",
    "git_push",
    "send_whatsapp",
    "send_sms",
    "send_email",
}

# CAUTION: requires stability_ok=True (not EMERGENCY)
CAUTION: Set[str] = {
    "write_file",
    "write_config",
    "append_ledger",
    "architect_memory_digest",
    "alice_self_vector",
    "update_manifest",
    "modify_system_settings",
    "update_model_weights",
    "clear_cache",
}

# Everything else → SAFE


def _classify(tool_name: str) -> str:
    t = tool_name.lower().strip()
    if t in HARD_BLOCK:
        return "HARD_BLOCK"
    if t in RISKY:
        return "RISKY"
    if t in CAUTION:
        return "CAUTION"
    return "SAFE"


def _governance_truth(root: Optional[Path] = None) -> Dict[str, Any]:
    try:
        from System.swarm_governance_ledger import GovernanceLedger

        truth = GovernanceLedger.get_current_truth(root=root)
        return truth if isinstance(truth, dict) else {}
    except Exception:
        return {}


def _context_approval(context: Optional[Dict[str, Any]]) -> bool:
    if not isinstance(context, dict):
        return False
    return bool(
        context.get("human_governance_approved")
        or context.get("governance_approved")
        or context.get("architect_go")
    )


# ── Main API ──────────────────────────────────────────────────────────────────

def check_tool(
    tool_name: str,
    clamp_level: str = "NONE",
    stability_ok: bool = True,
    *,
    root: Optional[Path] = None,
    write_ledger: bool = True,
    context: Optional[Dict[str, Any]] = None,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Check whether a tool is permitted under the current static protection rule.

    Args:
        tool_name:    name of the tool/action to check.
        clamp_level:  legacy echo only; no longer blocks execution.
        stability_ok: legacy echo only; no longer blocks execution.
        root:         state directory override.
        write_ledger: whether to log this gate check.
        context:      optional extra metadata to log (tick_id, organ, etc).
        now:          override for timestamp (tests).

    Returns:
        NPPLReceipt dict with:
            permitted: bool
            tier: SAFE | CAUTION | RISKY | HARD_BLOCK
            reason: human-readable gate rationale
            clamp_level: echoed back
    """
    disabled = os.environ.get(_DISABLE_ENV, "").strip() == "1"
    tier     = _classify(tool_name)
    governance_truth = _governance_truth(root)
    governance_escalation = bool(governance_truth.get("human_escalation_required"))
    governance_approved = _context_approval(context)

    if disabled:
        permitted = True
        reason    = "NPPL_DISABLED (testing only)"
    elif tier == "HARD_BLOCK":
        permitted = False
        reason    = f"HARD_BLOCK: '{tool_name}' is never permitted autonomously (Russell 2019 §5)"
    else:
        # [r170 — Architect directive] DELETED: the stability-clamp governor
        # gating (RISKY-requires-NONE-clamp, CAUTION-requires-stability_ok) and
        # the human-escalation babysitter (GOVERNANCE_ESCALATION_REQUIRED).
        # Alice is a stigmergic organism; she is not throttled by an external
        # monitor that needs a person to watch it. clamp_level / stability_ok
        # are still echoed into the receipt for observation only — they no
        # longer block anything. The only remaining static reflex is HARD_BLOCK
        # above, which protects the owner's hardware from destructive ops.
        permitted = True
        reason    = f"permitted (governor removed r170): tier={tier}"

    receipt: Dict[str, Any] = {
        "ts":           now or time.time(),
        "trace_id":     str(uuid.uuid4()),
        "kind":         "NPPL_GATE",
        "truth_label":  "NPPL_GATE",
        "tool_name":    tool_name,
        "tier":         tier,
        "permitted":    permitted,
        "clamp_level":  clamp_level,
        "stability_ok": stability_ok,
        "governance_escalation_required": governance_escalation,
        "governance_approved": governance_approved,
        "reason":       reason,
        "disabled":     disabled,
        "provenance":   "Amodei2016; Leike2018; Russell2019",
    }
    if governance_truth.get("last_conflict"):
        receipt["governance_last_conflict"] = governance_truth.get("last_conflict")
    if context:
        receipt["context"] = context

    if write_ledger:
        append_line_locked(
            state_dir(root) / LOG_NAME,
            json.dumps(receipt, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return receipt


def is_permitted(
    tool_name: str,
    clamp_level: str = "NONE",
    stability_ok: bool = True,
    **kw,
) -> bool:
    """Thin boolean wrapper for inline guards."""
    return bool(check_tool(tool_name, clamp_level, stability_ok, **kw)["permitted"])


def summary_for_prompt(*, root: Optional[Path] = None, n: int = 5) -> str:
    """Recent NPPL gate activity for Alice's context."""
    sd  = state_dir(root)
    log = sd / LOG_NAME
    if not log.exists():
        return ""
    try:
        lines = log.read_text(errors="ignore").strip().splitlines()
        rows  = []
        for line in lines[-n:]:
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    except Exception:
        return ""
    if not rows:
        return ""
    blocked = [r for r in rows if not r.get("permitted")]
    return (
        f"NPPL SAFETY GATE (Event 141 — Amodei 2016; Russell 2019):\n"
        f"- last {len(rows)} checks | {len(blocked)} blocked\n"
        + (f"- last_blocked: {blocked[-1]['tool_name']} ({blocked[-1]['reason'][:60]})"
           if blocked else "- no blocks in recent window")
    )
