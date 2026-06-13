"""MCP receipt manifest: separate IDE MANA traces from Alice STGM proof."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List

TRUTH_LABEL = "MCP_STGM_RECEIPT_MANIFEST_V1"
MANIFEST_NAME = "mcp_receipt_manifest.json"

DEFAULT_TOOL_ROWS: tuple[Dict[str, Any], ...] = (
    {
        "tool": "get_ledger",
        "category": "read_only",
        "world_touch": False,
        "writes_ledger": False,
        "external_spend": False,
    },
    {
        "tool": "get_agent_status",
        "category": "read_only",
        "world_touch": False,
        "writes_ledger": False,
        "external_spend": False,
    },
    {
        "tool": "get_mcp_receipt_manifest",
        "category": "read_only",
        "world_touch": False,
        "writes_ledger": False,
        "external_spend": False,
    },
    {
        "tool": "propose_scar",
        "category": "ledger_mutation",
        "world_touch": True,
        "writes_ledger": True,
        "external_spend": False,
        "ledger": "repair_log.jsonl",
    },
    {
        "tool": "opencode.run",
        "category": "external_agent",
        "world_touch": True,
        "writes_ledger": False,
        "external_spend": True,
    },
    {
        "tool": "opencode.setup_grok_composer",
        "category": "setup_readout",
        "world_touch": False,
        "writes_ledger": False,
        "external_spend": False,
    },
    {
        "tool": "claude_cowork.local_setup",
        "category": "setup_readout",
        "world_touch": False,
        "writes_ledger": False,
        "external_spend": False,
    },
    {
        "tool": "ollama.list_local_models",
        "category": "local_probe",
        "world_touch": False,
        "writes_ledger": False,
        "external_spend": False,
    },
    {
        "tool": "ollama.chat_local",
        "category": "local_inference",
        "world_touch": True,
        "writes_ledger": False,
        "external_spend": False,
    },
    {
        "tool": "grok.oauth_chat",
        "category": "external_inference",
        "world_touch": True,
        "writes_ledger": True,
        "external_spend": True,
    },
    {
        "tool": "grok.build_cli",
        "category": "external_agent",
        "world_touch": True,
        "writes_ledger": True,
        "external_spend": True,
    },
)


def _state_dir(state_dir: Path | str | None) -> Path:
    if state_dir is None:
        return Path(__file__).resolve().parents[1] / ".sifta_state"
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def _manifest_tool_row(row: Dict[str, Any]) -> Dict[str, Any]:
    world_touch = bool(row.get("world_touch"))
    return {
        **row,
        "requires_owner_nonce": world_touch,
        "doctor_trace_currency": "MANA",
        "doctor_trace_crypto": False,
        "stgm_spend_proof": "required_before_execution" if world_touch else "not_required_for_read_only",
        "stgm_is_crypto": True,
        "mana_is_crypto": False,
        "receipt_boundary": (
            "MCP caller trace is MANA unless an Alice swimmer/hardware proof path "
            "validates the STGM spend receipt."
        ),
    }


def build_mcp_receipt_manifest(
    tools: Iterable[Dict[str, Any]] | None = None,
    *,
    generated_by: str = "sifta_mcp_server",
) -> Dict[str, Any]:
    rows = [_manifest_tool_row(dict(row)) for row in (tools or DEFAULT_TOOL_ROWS)]
    return {
        "schema": TRUTH_LABEL,
        "truth_label": TRUTH_LABEL,
        "generated_ts": time.time(),
        "generated_by": generated_by,
        "economy_boundary": {
            "MANA": {
                "crypto": False,
                "scope": "IDE coordination trace; forgeable; never counts as Alice STGM.",
            },
            "STGM": {
                "crypto": True,
                "scope": "Alice swimmer / owner-silicon spend proof; no double-spend lane.",
            },
        },
        "tools": rows,
        "summary": {
            "tool_count": len(rows),
            "owner_nonce_required": sum(1 for row in rows if row["requires_owner_nonce"]),
            "mana_is_crypto": False,
            "stgm_is_crypto": True,
        },
    }


def write_mcp_receipt_manifest(
    *,
    state_dir: Path | str | None = None,
    tools: Iterable[Dict[str, Any]] | None = None,
    generated_by: str = "sifta_mcp_server",
) -> Dict[str, Any]:
    manifest = build_mcp_receipt_manifest(tools, generated_by=generated_by)
    sd = _state_dir(state_dir)
    sd.mkdir(parents=True, exist_ok=True)
    path = sd / MANIFEST_NAME
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {**manifest, "manifest_path": str(path)}


def mcp_receipt_manifest_text(*, state_dir: Path | str | None = None) -> str:
    return json.dumps(write_mcp_receipt_manifest(state_dir=state_dir), sort_keys=True)


def _tool_manifest_row(tool_name: str) -> Dict[str, Any] | None:
    manifest = build_mcp_receipt_manifest()
    for row in manifest.get("tools", []):
        if row.get("tool") == tool_name:
            return row
    return None


def _append_enforcement_row(sd: Path, row: Dict[str, Any]) -> None:
    path = sd / "effector_gate.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")


def enforce_mcp_tool_call(
    tool_name: str,
    *,
    tool_args: Dict[str, Any] | None = None,
    state_dir: Path | str | None = None,
) -> Dict[str, Any]:
    """Block world-touching MCP tools without owner nonce / STGM spend proof (r1079)."""
    import os
    import uuid

    if os.environ.get("SIFTA_MCP_SKIP_MANIFEST_ENFORCE", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }:
        return {"ok": True, "enforced": False, "reason": "skip_env"}

    row = _tool_manifest_row(tool_name)
    if row is None:
        return {"ok": True, "enforced": False, "reason": "tool_not_in_manifest"}

    if not row.get("world_touch"):
        return {"ok": True, "enforced": True, "lane": "read_only", "tool": tool_name}

    from System.swarm_effector_gate import read_active_context
    from System.swarm_intent_nonce_gate import validate_effector_spend

    sd = _state_dir(state_dir)
    args = dict(tool_args or {})
    ctx = read_active_context(state_dir=sd)
    effector = f"mcp:{tool_name}"

    if ctx.get("recovery_only"):
        reason = "recovery_context_no_effector"
        _append_enforcement_row(
            sd,
            {
                "schema": "MCP_MANIFEST_ENFORCE_V1",
                "action": "refused",
                "receipt_id": str(uuid.uuid4()),
                "ts": time.time(),
                "effector": effector,
                "reason": reason,
                "tool": tool_name,
                "manifest_row": row,
            },
        )
        return {"ok": False, "reason": reason, "tool": tool_name, "manifest_row": row}

    nonce = str(args.get("owner_nonce") or ctx.get("nonce") or "").strip()
    if not nonce:
        reason = "mcp_world_touch_requires_owner_nonce"
        _append_enforcement_row(
            sd,
            {
                "schema": "MCP_MANIFEST_ENFORCE_V1",
                "action": "refused",
                "receipt_id": str(uuid.uuid4()),
                "ts": time.time(),
                "effector": effector,
                "reason": reason,
                "tool": tool_name,
                "manifest_row": row,
                "hint": "bind_owner_ingress first or pass owner_nonce in tool arguments",
            },
        )
        return {
            "ok": False,
            "reason": reason,
            "tool": tool_name,
            "manifest_row": row,
            "hint": "bind_owner_ingress first or pass owner_nonce in tool arguments",
        }

    spend = validate_effector_spend(nonce, state_dir=sd, effector=effector)
    if not spend.get("ok"):
        reason = str(spend.get("reason") or "spend_denied")
        _append_enforcement_row(
            sd,
            {
                "schema": "MCP_MANIFEST_ENFORCE_V1",
                "action": "refused",
                "receipt_id": str(uuid.uuid4()),
                "ts": time.time(),
                "effector": effector,
                "reason": reason,
                "tool": tool_name,
                "nonce": nonce,
                "spend": spend,
            },
        )
        return {"ok": False, "reason": reason, "tool": tool_name, "nonce": nonce, "spend": spend}

    _append_enforcement_row(
        sd,
        {
            "schema": "MCP_MANIFEST_ENFORCE_V1",
            "action": "allowed",
            "receipt_id": str(uuid.uuid4()),
            "ts": time.time(),
            "effector": effector,
            "tool": tool_name,
            "nonce": nonce,
            "stgm_spend_proof": row.get("stgm_spend_proof"),
            "mana_is_crypto": False,
            "stgm_is_crypto": True,
        },
    )
    return {
        "ok": True,
        "enforced": True,
        "lane": "STGM_SPEND_PROOF",
        "tool": tool_name,
        "nonce": nonce,
        "spend": spend,
    }


__all__ = [
    "TRUTH_LABEL",
    "MANIFEST_NAME",
    "DEFAULT_TOOL_ROWS",
    "build_mcp_receipt_manifest",
    "write_mcp_receipt_manifest",
    "mcp_receipt_manifest_text",
    "enforce_mcp_tool_call",
]
