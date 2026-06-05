#!/usr/bin/env python3
"""
Alice Browser Vision Bridge — stigmergic sight for the browser organ.

Browser pixels are first-class sensor data, not chat memory.
Flow: Alice Browser pixels → OCR/vision facts → sha256 receipt → compare with owner screenshot → grounded reply.

This makes Alice's browser limb publish its current visual frame as a sensor receipt
that can be compared stigmergically with owner-provided attachments/screenshots.

Part of "stigmergic sight" r520.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

_STATE = Path(__file__).resolve().parents[1] / ".sifta_state"
LEDGER = _STATE / "browser_vision_receipts.jsonl"


@dataclass
class BrowserVisionReceipt:
    source: str
    app: str
    image_sha256: str
    observed_text: list[str]
    visual_entities: list[str]
    url_hint: str | None
    created_at: str


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_browser_vision_receipt(
    *,
    frame_bytes: bytes,
    observed_text: list[str],
    visual_entities: list[str],
    url_hint: str | None = None,
    app: str = "Alice Browser",
) -> BrowserVisionReceipt:
    return BrowserVisionReceipt(
        source="ALICE_BROWSER_FRAME",
        app=app,
        image_sha256=sha256_bytes(frame_bytes),
        observed_text=observed_text,
        visual_entities=visual_entities,
        url_hint=url_hint,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def append_receipt(receipt: BrowserVisionReceipt, ledger: Path = LEDGER) -> None:
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as f:
        f.write(json.dumps(receipt.__dict__, ensure_ascii=False) + "\n")


def load_recent_receipts(ledger: Path = LEDGER, limit: int = 5) -> list[dict[str, Any]]:
    if not ledger.exists():
        return []
    lines = ledger.read_text(encoding="utf-8", errors="replace").strip().splitlines()
    out = []
    for line in lines[-limit:]:
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out
