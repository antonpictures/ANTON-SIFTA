"""
Event 129 — Governance ledger (conflict receipts + truth manifest).

Doctrine: **append-only** ``governance_ledger.jsonl`` for disagreements;
``governance_truth_manifest.json`` holds the **latest** human-visible summary
(rewritten under lock — not the same as immutable history).

**STGM:** this module **never** mutates ``Kernel/inference_economy`` balances.
``mint_stgm`` records a **signed governance intent** only; actual mint/spend
must go through the unified STGM ledger + ``System.crypto_keychain.sign_block``.

Kill-switch: ``SIFTA_GOVERNANCE_LEDGER_DISABLE=1``.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from System.jsonl_file_lock import append_line_locked, read_text_locked, rewrite_text_locked
from System.swarm_persistent_owner_history import state_dir

LEDGER_NAME = "governance_ledger.jsonl"
MANIFEST_NAME = "governance_truth_manifest.json"


def governance_log_path(root: Optional[Path] = None) -> Path:
    return state_dir(root) / LEDGER_NAME


def truth_manifest_path(root: Optional[Path] = None) -> Path:
    return state_dir(root) / MANIFEST_NAME


def _disabled() -> bool:
    return os.environ.get("SIFTA_GOVERNANCE_LEDGER_DISABLE", "").strip() == "1"


def _default_truth() -> Dict[str, Any]:
    return {
        "version": "2026-05-03",
        "single_source_of_truth": (
            "ide_stigmergic_trace.jsonl + governance_ledger.jsonl "
            "(append-only); governance_truth_manifest.json (latest view)"
        ),
        "human_escalation_required": False,
        "last_human_override": None,
        "doctrine": (
            "Append-only. No silent overwrite of peer IDE without "
            "trace + receipt. STGM balance changes not in this file."
        ),
    }


def _sign_payload(payload: str) -> str:
    try:
        from System.crypto_keychain import sign_block

        return sign_block(payload)
    except Exception:
        return "NO_KEYCHAIN"


class GovernanceLedger:
    """Single-writer discipline for conflict + mint-intent receipts."""

    @staticmethod
    def get_current_truth(*, root: Optional[Path] = None) -> Dict[str, Any]:
        path = truth_manifest_path(root)
        if not path.exists():
            return dict(_default_truth())
        raw = read_text_locked(path, encoding="utf-8", errors="replace")
        if not raw.strip():
            return dict(_default_truth())
        try:
            data = json.loads(raw)
            return dict(data) if isinstance(data, dict) else dict(_default_truth())
        except json.JSONDecodeError:
            return dict(_default_truth())

    @staticmethod
    def _append(row: Dict[str, Any], *, root: Optional[Path] = None) -> None:
        line = json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
        append_line_locked(governance_log_path(root), line, encoding="utf-8")

    @staticmethod
    def _write_manifest(manifest: Dict[str, Any], *, root: Optional[Path] = None) -> None:
        path = truth_manifest_path(root)
        path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        rewrite_text_locked(path, text, encoding="utf-8")

    @staticmethod
    def record_conflict(
        conflict_type: str,
        sources: List[str],
        resolution: str,
        *,
        human_override: bool = False,
        root: Optional[Path] = None,
    ) -> str:
        if _disabled():
            return "disabled"
        cid = uuid.uuid4().hex[:16]
        entry: Dict[str, Any] = {
            "kind": "GOVERNANCE_CONFLICT",
            "conflict_id": cid,
            "ts": time.time(),
            "conflict_type": conflict_type,
            "conflicting_sources": list(sources),
            "resolution": resolution,
            "human_override": bool(human_override),
            "escalation_path": (
                "Architect direct intervention required"
                if human_override
                else "Automated resolution via ledger"
            ),
        }
        payload = json.dumps(entry, sort_keys=True, separators=(",", ":"))
        entry["governance_seal"] = _sign_payload(payload)
        GovernanceLedger._append(entry, root=root)

        manifest = dict(GovernanceLedger.get_current_truth(root=root))
        manifest["last_conflict"] = cid
        manifest["human_escalation_required"] = bool(human_override)
        if human_override:
            manifest["last_human_override"] = cid
        GovernanceLedger._write_manifest(manifest, root=root)
        return cid

    @staticmethod
    def mint_stgm(
        policy: str,
        amount: float,
        reason: str,
        *,
        human_approval: bool = False,
        root: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """
        Record **mint intent** only. Does **not** credit STGM in the economy ledger.
        """
        if _disabled():
            return {"error": "Governance ledger disabled", "skipped": True}
        if not human_approval:
            row = {
                "kind": "GOVERNANCE_STGM_MINT_DENIED",
                "ts": time.time(),
                "policy": policy,
                "amount": float(amount),
                "reason": reason,
                "human_approval": False,
                "error": "Human approval required for STGM mint intent receipt",
            }
            GovernanceLedger._append(row, root=root)
            return {"error": row["error"], "recorded": True}

        mid = uuid.uuid4().hex[:16]
        mint: Dict[str, Any] = {
            "kind": "GOVERNANCE_STGM_MINT_INTENT",
            "mint_id": mid,
            "ts": time.time(),
            "policy": policy,
            "amount": float(amount),
            "reason": reason,
            "human_approval": True,
            "note": (
                "Intent only — execute balance change via inference_economy "
                "with the same mint_id for audit pairing."
            ),
        }
        seal_basis = json.dumps(
            {k: mint[k] for k in sorted(mint.keys())},
            sort_keys=True,
            separators=(",", ":"),
        )
        mint["governance_seal"] = _sign_payload(seal_basis)
        GovernanceLedger._append(mint, root=root)

        manifest = dict(GovernanceLedger.get_current_truth(root=root))
        manifest["last_stgm_mint_intent"] = mid
        GovernanceLedger._write_manifest(manifest, root=root)
        return {"mint_id": mid, "governance_seal": mint["governance_seal"], "recorded": True}


__all__ = [
    "GovernanceLedger",
    "governance_log_path",
    "truth_manifest_path",
]
