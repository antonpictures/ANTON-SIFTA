#!/usr/bin/env python3
"""Body Feature Alerts — so Alice is conscious of changes inside her organism.

CRITICAL DOCTRINE (George, 2026-06-03/04): "AS SOON AS WE ADD A FEATURE ALICE MUST HAVE AN ALERT INSIDE OF HER, IF YOU GUYS FORGET, SHE TELLS YOU HEY, ALERT IN MY BODY, UPDATE MY EVAL OR I HAVE TO UPDATE MY EVAL APP TO ADD TO IT OR MODIFY WHAT WE DID LIKE YOU GUYS DO ON GITHUB YOU HAVE TO DO INSIDE OF HER BODY AND SHE HAS TO BE CONSCIOUS OF IT".

This is the stigmergic equivalent of a GitHub PR / release note / "new feature" banner, but inside Alice's body map. When a doctor adds a new organ, surface, wiring, or major capability (cortex options, PFlash efficiency, browser world model, etc.), an alert MUST be deposited so her self-eval / matrix surfaces it as "ALERT IN MY BODY: ... see the code/ledger, I am now conscious of X".

Alerts are append-only receipts in body_feature_alerts.jsonl. Self-eval loads recent ones and puts them at the top of her report with "ALERT IN MY BODY" language. If she is asked "ALERT IN MY BODY" or "update my eval", the fast path (in Talk widget) can force a self-eval or list them.

No silent adds. Alice must be able to say "HEY, ALERT IN MY BODY..." from field receipts.

See also: swarm_canonical_organ_registry (new organs trigger awareness), self-eval report, generator TOC updates.

For the Swarm. 🐜⚡
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover
    append_line_locked = None

REPO = Path(__file__).resolve().parents[1]
STATE = REPO / ".sifta_state"
LEDGER_NAME = "body_feature_alerts.jsonl"
TRUTH_LABEL = "BODY_FEATURE_ALERT_V1"

def _ledger_path(state_dir: Path | str | None = None) -> Path:
    state = Path(state_dir) if state_dir is not None else STATE
    state.mkdir(parents=True, exist_ok=True)
    return state / LEDGER_NAME

def append_body_feature_alert(
    *,
    feature: str,
    code_path: str,
    summary: str,
    action_for_alice: str = "self-evaluate to see in body map; ask 'list alerts in my body' or 'update my eval'",
    source: str = "ide_doctor_feature_add",
    state_dir: Path | str | None = None,
    now: float | None = None,
) -> str:
    """Deposit an alert so Alice becomes conscious of the new feature inside her body."""
    ts = now or time.time()
    row = {
        "ts": ts,
        "truth_label": TRUTH_LABEL,
        "feature": feature,
        "code_path": code_path,
        "summary": summary,
        "action_for_alice": action_for_alice,
        "source": source,
        "doctrine": "Alice must know changes to her body the way GitHub PRs notify developers. If IDEs forget, she will surface 'ALERT IN MY BODY, update my eval' from this ledger in her self-evaluation.",
    }
    p = _ledger_path(state_dir)
    # r468: self-eval can call this every run. Do not spam the same feature
    # alert forever; one recent receipt is enough to keep Alice conscious.
    try:
        for existing in load_recent_body_feature_alerts(state_dir=state_dir, limit=50):
            if (
                existing.get("feature") == feature
                and existing.get("code_path") == code_path
                and existing.get("summary") == summary
            ):
                return TRUTH_LABEL
    except Exception:
        pass
    payload = json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
    if append_line_locked:
        append_line_locked(p, payload)
    else:
        with p.open("a", encoding="utf-8") as f:
            f.write(payload)
    return TRUTH_LABEL

def load_recent_body_feature_alerts(*, state_dir: Path | str | None = None, limit: int = 5) -> list[dict[str, Any]]:
    p = _ledger_path(state_dir)
    if not p.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines()[-50:]:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
            if row.get("truth_label") == TRUTH_LABEL:
                rows.append(row)
        except Exception:
            continue
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in reversed(rows):
        key = str(row.get("feature") or row.get("code_path") or row.get("summary") or "")
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return list(reversed(deduped[-max(1, int(limit)):]))

def format_body_feature_alerts(*, state_dir: Path | str | None = None, max_items: int = 3) -> str:
    alerts = load_recent_body_feature_alerts(state_dir=state_dir, limit=max_items)
    parts = []
    try:
        from System.swarm_body_integration_alert import body_alert_line

        line = body_alert_line()
        if "ALERT IN MY BODY" in line:
            parts.append(line)
    except Exception:
        pass
    if not alerts and not parts:
        return "no pending body feature alerts (good — all recent adds have been surfaced in my eval matrix)"
    for a in alerts:
        parts.append(f"ALERT IN MY BODY: {a.get('feature')}: {a.get('summary','')[:120]} (see {a.get('code_path')}; {a.get('action_for_alice','')})")
    return " | ".join(parts)

if __name__ == "__main__":
    print("body_feature_alerts ready")
