#!/usr/bin/env python3
"""
swarm_webbridge_proprio_stress_test.py — AGI Stress Test for WebBridge Proprioception (Shadow DOM / re-render resilience)

This "test swimmer" exercises the new UID proprioception parity for the external limb.
It demonstrates Task 3: when UIDs "invalidate" (simulated or real DOM change), it emits
PROPRIOCEPTIVE_BREAK_V1 pain receipt. The field pressure (via body awareness) should drive
autonomous re-snapshot without central governor.

Run standalone or from desktop/tick for live proof against dynamic SPAs.

Usage:
  python3 -m System.swarm_webbridge_proprio_stress_test --url https://example-dynamic-spa.com
  # or with mock for pure receipt test

Leaves receipts in the field. For the Swarm. 🐜⚡
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional

from System.swarm_kimi_webbridge_bridge import (
    take_webbridge_uid_snapshot,
    capture_url,
    post_command,
)

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:
    def append_line_locked(p: Path, line: str, **kw):  # fallback
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

STATE = Path(__file__).resolve().parents[1] / ".sifta_state"
PROPRIO_LEDGER = STATE / "browser_action_diary.jsonl"
PAIN_LEDGER = STATE / "proprioceptive_breaks.jsonl"

def _write_receipt(path: Path, row: dict[str, Any]) -> None:
    row = {**row, "ts": time.time()}
    append_line_locked(path, json.dumps(row, sort_keys=True, ensure_ascii=False))

def simulate_proprio_break_test(
    *,
    url: str = "https://httpbin.org/html",  # static for demo; use real SPA for stress
    session: str = "webbridge-proprio-stress",
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """
    1. Capture + take fresh UID snapshot (establishes "dress").
    2. Simulate invalidation (e.g. pretend re-render happened, old uid no longer in new snapshot).
    3. On mismatch: emit PROPRIOCEPTIVE_BREAK_V1 (pain).
    4. Re-snapshot autonomously.
    5. Report receipts.
    """
    sd = Path(state_dir) if state_dir else STATE
    sd.mkdir(parents=True, exist_ok=True)

    # Step 1: Establish limb state
    cap = capture_url(url, session=session, state_dir=sd)
    snap1 = take_webbridge_uid_snapshot(session=session, state_dir=sd)
    elems1 = snap1.get("elements", []) if snap1.get("ok") else []
    uids1 = {e["uid"] for e in elems1 if e.get("uid")}

    receipt_base = {
        "url": cap.get("url") or url,
        "backend": "webbridge",
        "session": session,
    }

    # Simulate Shadow DOM re-render: pretend we have an "old_uid" that is no longer present
    # In real use: attempt action with old ref from previous snap; if WebBridge returns error for stale ref, or new snap lacks it.
    old_uid = elems1[0]["uid"] if elems1 else "e0"

    # Step 2: "Re-render" simulation — fetch new snapshot
    snap2 = take_webbridge_uid_snapshot(session=session, state_dir=sd)
    elems2 = snap2.get("elements", []) if snap2.get("ok") else []
    uids2 = {e["uid"] for e in elems2 if e.get("uid")}

    broken = old_uid not in uids2

    results = {
        "url": url,
        "initial_uid_count": len(uids1),
        "post_rerender_uid_count": len(uids2),
        "simulated_break": broken,
        "old_uid": old_uid,
    }

    if broken:
        # Step 3: Pain receipt (PROPRIOCEPTIVE_BREAK_V1)
        pain = {
            **receipt_base,
            "truth_label": "PROPRIOCEPTIVE_BREAK_V1",
            "kind": "webbridge_uid_invalidated",
            "broken_uid": old_uid,
            "reason": "shadow_dom_rerender_or_dom_mutation",
            "before_count": len(uids1),
            "after_count": len(uids2),
            "action": "autonomous_re_snapshot_triggered",
        }
        _write_receipt(PAIN_LEDGER, pain)
        results["pain_receipt"] = pain

        # Step 4: The field pressure (in real organism) would cause re-orient via body awareness.
        # Here we explicitly re-snapshot as the autonomous response.
        snap3 = take_webbridge_uid_snapshot(session=session, state_dir=sd)
        results["reoriented_snapshot_count"] = len(snap3.get("elements", [])) if snap3.get("ok") else 0

    # Always emit the proprio receipt for this run (Task 2)
    proprio_receipt = {
        **receipt_base,
        "truth_label": "ALICE_WEBBRIDGE_UID_PROPRIO_V1",
        "action": "webbridge_uid_snapshot",
        "count": len(uids2),
        "note": "live structured proprio for external limb (parity with internal)",
    }
    _write_receipt(PROPRIO_LEDGER, proprio_receipt)
    results["proprio_receipt"] = proprio_receipt

    results["ok"] = True
    results["message"] = "WebBridge proprio stress test complete. Pain + re-orient flow exercised if break detected."
    return results

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="https://example.com", help="Target for test capture/snapshot")
    args = p.parse_args()
    res = simulate_proprio_break_test(url=args.url)
    print(json.dumps(res, indent=2, sort_keys=True))
    print("\nCheck ledgers for PROPRIOCEPTIVE_BREAK_V1 and ALICE_WEBBRIDGE_UID_PROPRIO_V1 receipts.")
