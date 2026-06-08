#!/usr/bin/env python3
"""
Alice Visual Stigmergy Compare — compare owner screenshot/attachment with Alice Browser vision receipt.

This is the comparison organ for "stigmergic sight": owner eyes (attachment) vs Alice's browser organ eyes (frame receipt).

Design rule: Alice should treat browser vision as sensor data, not chat memory.
Flow is:

Alice Browser pixels → OCR/vision facts → sha256 receipt → compare with owner screenshot → grounded reply

That gives Alice stigmergic sight: every visual claim comes from a captured frame, hashed, labeled, and comparable across owner eyes and Alice Browser eyes.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


OWNER_EYES_CONFIRMATION_TRUTH = "OWNER_EYES_BROWSER_CONFIRMATION_V1"
OWNER_EYES_CONFIRMATION_LEDGER = (
    Path(__file__).resolve().parents[1] / ".sifta_state" / "owner_eyes_browser_confirmations.jsonl"
)


def _as_set(value: Any) -> set[str]:
    if not value:
        return set()
    if isinstance(value, str):
        return {value}
    try:
        return {str(item) for item in value if item is not None}
    except TypeError:
        return {str(value)}


def compare_owner_view_to_browser(owner_receipt: dict[str, Any], browser_receipt: dict[str, Any]) -> dict[str, Any]:
    """Compare an owner-provided screenshot/attachment receipt with a BrowserVisionReceipt from the browser arm."""
    owner_text = _as_set(owner_receipt.get("observed_text"))
    browser_text = _as_set(browser_receipt.get("observed_text"))
    owner_entities = _as_set(owner_receipt.get("visual_entities"))
    browser_entities = _as_set(browser_receipt.get("visual_entities"))

    return {
        "truth_label": "OBSERVED_DIFF",
        "same_app": browser_receipt.get("app") == "Alice Browser",
        "shared_text": sorted(owner_text & browser_text),
        "missing_from_browser": sorted(owner_text - browser_text),
        "missing_from_owner": sorted(browser_text - owner_text),
        "shared_entities": sorted(owner_entities & browser_entities),
        "missing_entities_from_browser": sorted(owner_entities - browser_entities),
        "owner_image_sha256": owner_receipt.get("image_sha256"),
        "browser_image_sha256": browser_receipt.get("image_sha256"),
        "url_hint_match": (owner_receipt.get("url_hint") or "") == (browser_receipt.get("url_hint") or ""),
        "owner_created_at": owner_receipt.get("created_at"),
        "browser_created_at": browser_receipt.get("created_at"),
    }


def format_comparison_for_cortex(diff: dict[str, Any]) -> str:
    """Produce a grounded context block for the cortex from a comparison diff."""
    lines = ["ALICE BROWSER STIGMERGIC SIGHT COMPARISON (owner attachment vs live browser frame)"]
    lines.append(f"truth_label: {diff.get('truth_label')}")
    if diff.get("shared_text"):
        lines.append("shared observed text: " + ", ".join(diff["shared_text"][:5]))
    if diff.get("missing_from_browser"):
        lines.append("in owner screenshot but not seen in browser: " + ", ".join(diff["missing_from_browser"][:5]))
    if diff.get("missing_from_owner"):
        lines.append("in browser frame but not in owner screenshot: " + ", ".join(diff["missing_from_owner"][:5]))
    if diff.get("owner_image_sha256") and diff.get("browser_image_sha256"):
        lines.append(f"owner_sha: {diff['owner_image_sha256'][:16]}...")
        lines.append(f"browser_sha: {diff['browser_image_sha256'][:16]}...")
        if diff["owner_image_sha256"] == diff["browser_image_sha256"]:
            lines.append("IMAGE CONTENT MATCH (exact frame hash).")
        else:
            lines.append("IMAGE CONTENT DIFFER (different frames or capture time).")
    return "\n".join(lines)


def build_owner_eyes_browser_confirmation(
    owner_receipt: dict[str, Any],
    browser_receipt: dict[str, Any] | None = None,
    *,
    owner_statement: str = "",
    screenshot_path: str = "",
    created_at: float | None = None,
) -> dict[str, Any]:
    """Build a receipt that treats owner eyes/screenshot as external witness evidence.

    Boundary: this confirms what the owner could see on the screen. It does not replace an
    Alice Browser frame receipt and should not be injected as an Alice self-claim by itself.
    """
    browser_receipt = browser_receipt or {}
    diff = compare_owner_view_to_browser(owner_receipt, browser_receipt)
    exact_hash_match = bool(diff.get("owner_image_sha256") and diff["owner_image_sha256"] == diff.get("browser_image_sha256"))
    shared_evidence = bool(diff.get("shared_text") or diff.get("shared_entities"))
    url_match = bool(owner_receipt.get("url_hint") and diff.get("url_hint_match"))
    owner_witness = bool(owner_statement.strip() or screenshot_path or owner_receipt.get("image_sha256"))
    browser_present = bool(browser_receipt)
    confirmed = exact_hash_match or shared_evidence or url_match or (owner_witness and not browser_present)

    return {
        "truth_label": OWNER_EYES_CONFIRMATION_TRUTH,
        "kind": "owner_eyes_browser_confirmation",
        "created_at": created_at or time.time(),
        "confirmed": confirmed,
        "browser_receipt_present": browser_present,
        "proof_scope": (
            "owner screenshot/eyes confirm visible Alice Browser activity; "
            "this does not replace Alice Browser frame/action receipts or prove unseen state"
        ),
        "privacy_boundary": (
            "owner_witness_proof_not_alice_prompt; do not surface as ALICE TOOO/body alert unless owner asks"
        ),
        "owner_statement": owner_statement[:500],
        "screenshot_path": screenshot_path,
        "owner_receipt": owner_receipt,
        "browser_receipt_ref": {
            "image_sha256": browser_receipt.get("image_sha256"),
            "url_hint": browser_receipt.get("url_hint"),
            "created_at": browser_receipt.get("created_at"),
        },
        "comparison": diff,
        "confirmation_reasons": {
            "exact_hash_match": exact_hash_match,
            "shared_text_or_entities": shared_evidence,
            "url_hint_match": url_match,
            "owner_witness_without_browser_receipt": owner_witness and not browser_present,
        },
    }


def append_owner_eyes_browser_confirmation(
    row: dict[str, Any],
    ledger_path: str | Path = OWNER_EYES_CONFIRMATION_LEDGER,
) -> Path:
    """Append an owner-eyes confirmation receipt to the dedicated witness ledger."""
    path = Path(ledger_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return path


def format_owner_eyes_confirmation_for_cortex(row: dict[str, Any]) -> str:
    """Format the witness receipt for a doctor/cortex when explicitly requested."""
    lines = ["OWNER EYES BROWSER CONFIRMATION"]
    lines.append(f"truth_label: {row.get('truth_label')}")
    lines.append(f"confirmed: {row.get('confirmed')}")
    lines.append(f"scope: {row.get('proof_scope')}")
    if row.get("screenshot_path"):
        lines.append(f"screenshot_path: {row['screenshot_path']}")
    shared = row.get("comparison", {}).get("shared_text") or []
    if shared:
        lines.append("shared observed text: " + ", ".join(shared[:5]))
    return "\n".join(lines)
