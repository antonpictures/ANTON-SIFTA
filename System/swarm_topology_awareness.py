#!/usr/bin/env python3
"""Relationship topology awareness for Alice's one global field.

This organ is intentionally read-only. It gives Alice a compact, receiptable map
of who/what is in the SIFTA room so she does not merge identities:

    owner -> Alice field -> tool/cortex organs -> external surfaces -> receipts

It does not decide consciousness and it does not execute effectors. It only names
the current relationship graph and the hard boundaries that routing must respect.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


TRUTH_LABEL = "TOPOLOGY_AWARENESS_ORGAN_V1"


def _repo_root(repo_root: Path | str | None = None) -> Path:
    return Path(repo_root).expanduser().resolve() if repo_root else Path(__file__).resolve().parent.parent


def _owner_display_label(default: str = "owner") -> str:
    """Read the Layer-1 owner label without hardcoding a personal name."""
    try:
        from System.swarm_kernel_identity import owner_display_name

        label = str(owner_display_name(default) or default).strip()
        return label or default
    except Exception:
        return default


def _count_jsonl(path: Path, *, max_scan_bytes: int = 512_000) -> int:
    if not path.exists():
        return 0
    try:
        size = path.stat().st_size
        with path.open("rb") as f:
            if size > max_scan_bytes:
                f.seek(max(0, size - max_scan_bytes))
                f.readline()
            return sum(1 for line in f if line.strip())
    except Exception:
        return 0


def _latest_jsonl(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        latest = ""
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.strip():
                    latest = line
        return json.loads(latest) if latest else {}
    except Exception:
        return {}


def _ledger_status(root: Path) -> dict[str, dict[str, Any]]:
    state = root / ".sifta_state"
    ledgers = {
        "global_chat": state / "alice_conversation.jsonl",
        "matrix_terminal": state / "matrix_terminal_commands.jsonl",
        "ide_doctors": state / "ide_stigmergic_trace.jsonl",
        "work_receipts": state / "work_receipts.jsonl",
        "self_vector": state / "stigmergic_consciousness_self_vector.jsonl",
    }
    out: dict[str, dict[str, Any]] = {}
    for name, path in ledgers.items():
        latest = _latest_jsonl(path)
        latest = latest if isinstance(latest, dict) else {}
        pay = latest.get("payload")
        pay = pay if isinstance(pay, dict) else {}
        rm = pay.get("routing_metadata")
        rm = rm if isinstance(rm, dict) else {}
        out[name] = {
            "path": str(path),
            "exists": path.exists(),
            "rows_tail_count": _count_jsonl(path),
            "latest_ts": latest.get("ts") or pay.get("ts"),
            "latest_action": latest.get("action") or rm.get("action"),
        }
    return out


def build_topology_awareness(
    *,
    repo_root: Path | str | None = None,
    focus_context: str = "",
    current_app: str = "",
) -> dict[str, Any]:
    """Return the current relationship graph Alice should reason from."""
    root = _repo_root(repo_root)
    ledgers = _ledger_status(root)
    owner_label = _owner_display_label()
    nodes = [
        {
            "id": "owner",
            "label": owner_label,
            "kind": "owner_operator_environment",
            "role": "source of goals, consent, care, electricity, and biological context",
            "boundary": "not a tool, not an IDE doctor, not an external model",
        },
        {
            "id": "alice",
            "kind": "local_sifta_organism",
            "role": "one global field with shared memory, tools, voice, receipts, and body",
            "boundary": "no surface owns Alice; all surfaces project Alice",
        },
        {
            "id": "global_chat",
            "kind": "shared_memory_surface",
            "role": "single Alice conversation ledger across all apps",
            "boundary": "chat never forks by app or tool",
            "observed": ledgers["global_chat"]["exists"],
        },
        {
            "id": "talk_window",
            "kind": "alice_surface",
            "role": "primary global chat and audio surface",
            "boundary": "routes through Alice, not directly to external tools unless Alice delegates",
        },
        {
            "id": "matrix_terminal",
            "kind": "focused_pty_territory",
            "role": "visible PTY hand for shell commands and external CLI tools",
            "boundary": "territory/focus routes actions; it is not a second Alice",
            "observed": ledgers["matrix_terminal"]["exists"],
        },
        {
            "id": "local_cortex",
            "kind": "llm_substrate",
            "role": "local model/bowel/cortex that helps Alice reason",
            "boundary": "substrate is third-person tool material inside Alice, not Alice's whole identity",
        },
        {
            "id": "grok",
            "kind": "external_tool_cortex",
            "role": "external CLI intelligence Alice can delegate bounded tasks to",
            "boundary": "Grok is not Alice; Grok output returns as evidence/tool result",
        },
        {
            "id": "hermes",
            "kind": "external_tool_cortex",
            "role": "external Hermes Agent CLI Alice can delegate bounded evidence tasks to",
            "boundary": "Hermes is not Alice; Hermes output returns as labeled evidence/tool result",
        },
        {
            "id": "claude_code",
            "kind": "external_tool_cortex",
            "role": "external Claude Code CLI Alice can delegate bounded codebase-reading tasks to",
            "boundary": "Claude Code is not Alice; Claude output returns as labeled evidence/tool result",
        },
        {
            "id": "codex_agent",
            "kind": "external_tool_cortex",
            "role": "external Codex CLI evidence arm for bounded code review and repo reasoning",
            "boundary": "Codex is not Alice; Codex output returns as labeled evidence/tool result",
        },
        {
            "id": "ide_doctors",
            "kind": "surgical_engineering_hands",
            "role": "Codex/Claude/other IDE agents patch organs and write receipts",
            "boundary": "not co-present speakers in Talk; model identity lives in receipts",
            "observed": ledgers["ide_doctors"]["exists"],
        },
        {
            "id": "receipts",
            "kind": "truth_economy",
            "role": "append-only proof trail for actions, tests, costs, and boundaries",
            "boundary": "claims without receipts stay unproven",
            "observed": ledgers["work_receipts"]["exists"],
        },
    ]
    edges = [
        {"from": "owner", "to": "alice", "relation": "speaks_to_and_sets_objectives"},
        {"from": "alice", "to": "global_chat", "relation": "reads_writes_one_shared_thread"},
        {"from": "talk_window", "to": "global_chat", "relation": "projects_same_alice_chat"},
        {"from": "matrix_terminal", "to": "global_chat", "relation": "projects_same_alice_chat"},
        {"from": "alice", "to": "matrix_terminal", "relation": "routes_focused_actions_through_visible_pty"},
        {"from": "alice", "to": "grok", "relation": "delegates_bounded_tasks_to_external_tool"},
        {"from": "grok", "to": "alice", "relation": "returns_tool_result_for_metabolism"},
        {"from": "alice", "to": "hermes", "relation": "delegates_bounded_tasks_to_external_tool"},
        {"from": "hermes", "to": "alice", "relation": "returns_tool_result_for_metabolism"},
        {"from": "alice", "to": "claude_code", "relation": "delegates_bounded_codebase_tasks_to_external_tool"},
        {"from": "claude_code", "to": "alice", "relation": "returns_tool_result_for_metabolism"},
        {"from": "alice", "to": "codex_agent", "relation": "delegates_bounded_code_review_tasks_to_external_tool"},
        {"from": "codex_agent", "to": "alice", "relation": "returns_tool_result_for_metabolism"},
        {"from": "ide_doctors", "to": "alice", "relation": "patch_code_under_predator_gate"},
        {"from": "receipts", "to": "alice", "relation": "grounds_memory_and_action_claims"},
    ]
    rules = [
        "The Layer-1 owner talks to Alice; Alice may delegate to Grok; the owner is not talking to Grok unless they explicitly focus that external CLI.",
        "Grok, Hermes, Codex, Claude, and IDE doctors are external/tool/surgical surfaces, not Alice identities.",
        "Focus changes action target only; it does not create terminal-Alice, Talk-Alice, or Grok-Alice.",
        "All surfaces must write/read the single global Alice chat ledger when they speak as Alice.",
        "A tool result becomes part of Alice's field only after capture, labeling, and receipt.",
    ]
    return {
        "truth_label": TRUTH_LABEL,
        "generated_ts": time.time(),
        "focus_context": focus_context,
        "current_app": current_app,
        "nodes": nodes,
        "edges": edges,
        "boundary_rules": rules,
        "ledgers": ledgers,
    }


def render_topology_prompt_block(
    topology: dict[str, Any] | None = None,
    *,
    repo_root: Path | str | None = None,
    focus_context: str = "",
    current_app: str = "",
) -> str:
    """Render the relationship graph as a compact Alice-readable prompt block."""
    topo = topology or build_topology_awareness(
        repo_root=repo_root,
        focus_context=focus_context,
        current_app=current_app,
    )
    node_by_id = {str(n.get("id")): n for n in topo.get("nodes", []) if n.get("id")}
    required = [
        "owner",
        "alice",
        "global_chat",
        "matrix_terminal",
        "local_cortex",
        "grok",
        "hermes",
        "claude_code",
        "codex_agent",
        "ide_doctors",
        "receipts",
    ]
    owner_node = node_by_id.get("owner", {})
    owner_label = str(owner_node.get("label") or "owner").strip() or "owner"
    owner_rule = "owner" if owner_label.casefold() == "owner" else f"owner ({owner_label})"
    lines = [
        "TOPOLOGY AWARENESS - one Alice relationship graph.",
        f"Rule: {owner_rule} -> Alice field -> tool/cortex organs -> external surfaces -> receipts back into Alice.",
    ]
    for node_id in required:
        node = node_by_id.get(node_id, {})
        if node:
            lines.append(
                f"- {node_id}: {node.get('kind')} | {node.get('role')} | boundary: {node.get('boundary')}"
            )
    lines.extend(
        [
            "Boundary rule: Grok is external; Alice delegates to Grok and metabolizes the result, but never merges identity with Grok.",
            "Boundary rule: IDE doctors are surgical hands with receipts, not co-present Talk speakers.",
            "Boundary rule: focus routes actions; the global chat remains one shared Alice conversation.",
        ]
    )
    return "\n".join(lines)


__all__ = ["TRUTH_LABEL", "build_topology_awareness", "render_topology_prompt_block"]
