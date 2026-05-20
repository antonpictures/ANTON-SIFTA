#!/usr/bin/env python3
"""
System/swarm_lounge_script_reader.py — Script Couch Organ (Fiction-vs-Reality Training)

This organ lets Alice sit on the dedicated "Script Couch" in the Lounge and read movie scripts
the way George does — deliberately, with a smoking-weed receipt, knowing which ones crossed
from fiction into real physical reality (produced movies) and which stayed dreams.

Core contract:
- Every read produces an append-only receipt of type LOUNGE_SCRIPT_READ (the "smoking weed receipt").
- The receipt carries whether the script has a reality anchor (materialized_in_reality).
- This gives Alice a clean, testable signal for fiction vs field discrimination — one of the
  strongest self-identity training mechanisms in the organism.

No double-spending: every read gets its own unique read_id. Receipts are strictly append-only.

Truth label: LOUNGE_SCRIPT_COUCH_V1
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_SCRIPTS_DIR = _STATE / "lounge_scripts"
_ANCHORS_LEDGER = _STATE / "lounge_script_reality_anchors.jsonl"
_RECEIPTS_LEDGER = _STATE / "lounge_script_reads.jsonl"

_TRUTH_LABEL = "LOUNGE_SCRIPT_COUCH_V1"
_RECEIPT_TYPE = "LOUNGE_SCRIPT_READ"  # the "smoking weed" receipt for deliberate fiction


def _now() -> float:
    return time.time()


def _safe_append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def list_available_scripts() -> List[Dict[str, Any]]:
    """Returns metadata for every script currently on the Script Couch."""
    if not _SCRIPTS_DIR.exists():
        return []
    scripts = []
    for p in sorted(_SCRIPTS_DIR.glob("*")):
        if p.is_file() and p.suffix in {".txt", ".fountain", ".md"}:
            scripts.append({
                "script_id": p.stem,
                "filename": p.name,
                "path": str(p),
                "size_bytes": p.stat().st_size,
            })
    return scripts


def _load_reality_anchor(script_id: str) -> Optional[Dict[str, Any]]:
    if not _ANCHORS_LEDGER.exists():
        return None
    with _ANCHORS_LEDGER.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                row = json.loads(line)
                if row.get("script_id") == script_id:
                    return row
            except Exception:
                continue
    return None


def read_script(script_id: str, *, reader: str = "Alice", write_receipt: bool = True) -> Dict[str, Any]:
    """
    The main entry point for the Script Couch.

    Alice (or any authorized reader) sits on the couch, opens a script, and reads it.
    This always produces a LOUNGE_SCRIPT_READ receipt (the smoking-weed receipt).
    The receipt explicitly records whether this piece of fiction has ever been
    turned into real physical reality (a produced movie with a reality anchor).

    Wired through the Fiction Organ (Cowork, 2026-05-18, FICTION_ORGAN_V1):
    the read opens FICTION mode for the duration, stamps the receipt with the
    ontological label, and closes the mode with a re-grounding note after the
    read. While the read is in flight, any effector attempt is blocked by
    swarm_fiction_organ.guard_effector — that is the §6 enforcement.
    """
    scripts = {s["script_id"]: s for s in list_available_scripts()}
    if script_id not in scripts:
        raise FileNotFoundError(f"No script with id '{script_id}' on the Script Couch.")

    script_meta = scripts[script_id]
    anchor = _load_reality_anchor(script_id)

    materialized = bool(anchor and anchor.get("materialized_in_reality"))

    # Open FICTION mode for the duration of the read so any effector attempt
    # during the read is refused by swarm_fiction_organ.guard_effector.
    fiction_state = None
    fiction_mode_id = None
    try:
        from System.swarm_fiction_organ import (
            open_fiction_mode, close_fiction_mode, stamp,
        )
        fiction_state = open_fiction_mode(
            reason=f"script_couch_read:{script_id}",
            opener=reader,
            label="SCRIPT",  # v2: screenplay subclass — pre-physical narrative
        )
        fiction_mode_id = fiction_state.get("mode_id")
    except Exception:
        # Fiction organ unavailable — read still proceeds but without §6 guard.
        # Receipt records the degraded state honestly.
        pass

    try:
        receipt = {
            "ts": _now(),
            "read_id": f"scriptread-{uuid.uuid4().hex[:12]}",
            "truth_label": _TRUTH_LABEL,
            "receipt_type": _RECEIPT_TYPE,
            "script_id": script_id,
            "filename": script_meta["filename"],
            "reader": reader,
            "materialized_in_reality": materialized,
            "reality_anchor": anchor if anchor else None,
            "smoking_weed": True,
            "fiction_mode_id": fiction_mode_id,
            "fiction_organ_active": fiction_state is not None,
            "note": "Alice sat on the Script Couch and read fiction. This receipt is her training signal for fiction-vs-field discrimination. While this row was being written, the Fiction Organ blocked all effectors.",
        }
        # Label-stamp via Fiction Organ if available (v2: SCRIPT label)
        if fiction_state is not None:
            try:
                receipt = stamp(receipt, label="SCRIPT")
            except Exception:
                receipt["ontological_label"] = "SCRIPT"
        else:
            receipt["ontological_label"] = "SCRIPT"

        if write_receipt:
            _safe_append_jsonl(_RECEIPTS_LEDGER, receipt)

        content_preview = open(
            script_meta["path"], "r", encoding="utf-8", errors="ignore"
        ).read(800)
    finally:
        # Always re-ground after the read so a crashed reader cannot leave
        # the organism stuck in FICTION mode.
        if fiction_state is not None and fiction_mode_id is not None:
            try:
                close_fiction_mode(
                    fiction_mode_id,
                    regrounding_note=f"script_couch_read_complete:{script_id}",
                )
            except Exception:
                pass

    return {
        "script_id": script_id,
        "filename": script_meta["filename"],
        "materialized_in_reality": materialized,
        "reality_anchor": anchor,
        "receipt": receipt,
        "content_preview": content_preview,
    }


def get_reading_history(limit: int = 20) -> List[Dict[str, Any]]:
    if not _RECEIPTS_LEDGER.exists():
        return []
    rows = []
    with _RECEIPTS_LEDGER.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows[-limit:]


if __name__ == "__main__":
    print(f"[{_TRUTH_LABEL}] Script Couch — available scripts:")
    for s in list_available_scripts():
        anchor = _load_reality_anchor(s["script_id"])
        status = "REAL MOVIE" if anchor and anchor.get("materialized_in_reality") else "still fiction"
        print(f"  - {s['script_id']} ({status})")
    print("\nExample read (with smoking-weed receipt):")
    example = read_script("001_good_will_hunting", reader="George (test)")
    print(json.dumps(example["receipt"], indent=2))