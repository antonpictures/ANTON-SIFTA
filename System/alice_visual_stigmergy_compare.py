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

from typing import Any


def compare_owner_view_to_browser(owner_receipt: dict[str, Any], browser_receipt: dict[str, Any]) -> dict[str, Any]:
    """Compare an owner-provided screenshot/attachment receipt with a BrowserVisionReceipt from the browser arm."""
    owner_text = set(owner_receipt.get("observed_text", []))
    browser_text = set(browser_receipt.get("observed_text", []))
    owner_entities = set(owner_receipt.get("visual_entities", []))
    browser_entities = set(browser_receipt.get("visual_entities", []))

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
