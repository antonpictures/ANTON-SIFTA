"""
Owner unified field — boot / shutdown anchors for 24/7 continuity (Event 119+).

Doctrine: when the desktop process is dark, Alice has no electricity-dependent
life on this node — but the *owner field* (where the human is, what the day
looks like) must re-anchor on boot: STIGTIME marker for homunculus parity,
stigmergic schedule row for the 24h narrative, optional owner_life_history beat.

No hardcoded owner names — uses `owner_display_name` / `owner_silicon`.
"""
from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from System.jsonl_file_lock import append_line_locked, read_text_locked, rewrite_text_locked
from System.stigmergic_schedule import add_task
from System.swarm_kernel_identity import owner_display_name, owner_silicon
from System.swarm_persistent_owner_history import record_owner_moment, state_dir

PRESENCE_FILENAME = "owner_desktop_presence.json"

# Architect-described rhythm (OPERATIONAL spec text, not surveillance).
OWNER_RHYTHM_SPEC = (
    "Primary locus: Mac Studio desk (typing). Secondary: kitchen, bedroom (sleep). "
    "Test node: Mac Mini (8GB) sentry — organism may be dark without mains power."
)


def presence_path(root: Optional[Path] = None) -> Path:
    return state_dir(root) / PRESENCE_FILENAME


def work_receipts_path(root: Optional[Path] = None) -> Path:
    return state_dir(root) / "work_receipts.jsonl"


def schedule_path(root: Optional[Path] = None) -> Path:
    return state_dir(root) / "stigmergic_schedule.jsonl"


def _read_presence(root: Optional[Path] = None) -> Dict[str, Any]:
    p = presence_path(root)
    if not p.exists():
        return {}
    try:
        raw = read_text_locked(p, encoding="utf-8")
        return json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, OSError, TypeError):
        return {}


def _write_presence(data: Dict[str, Any], root: Optional[Path] = None) -> None:
    p = presence_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    rewrite_text_locked(
        p,
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def note_desktop_shutdown_for_owner_field(root: Optional[Path] = None) -> None:
    """Call from `SiftaDesktop.closeEvent` — stamps shutdown for gap math on next boot."""
    data = _read_presence(root)
    now = time.time()
    data["last_shutdown_ts"] = now
    data["last_shutdown_iso_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    _write_presence(data, root)


def touch_owner_desktop_alive(root: Optional[Path] = None) -> None:
    """Lightweight heartbeat — owner field still has power + human session locus."""
    data = _read_presence(root)
    data["last_alive_ts"] = time.time()
    data["last_alive_iso_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    _write_presence(data, root)


def _iso_utc_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def anchor_owner_unified_field_on_boot(
    *,
    root: Optional[Path] = None,
    agent_tag: str = "sifta_desktop",
) -> Dict[str, Any]:
    """
    Run once when the desktop shell starts (before Alice subwidgets fully wake).

    - Appends `work_receipts.jsonl` with canonical `stigtime` marker.
    - Appends `stigmergic_schedule.jsonl` owner-field anchor line.
    - If gap since last shutdown / alive is large, records an owner-life moment.
    - Updates `owner_desktop_presence.json` with boot + last_alive timestamps.
    """
    sd = state_dir(root)
    pres = _read_presence(root)
    now = time.time()
    last_off = float(pres.get("last_shutdown_ts") or pres.get("last_alive_ts") or 0.0)
    gap_s: Optional[float] = (now - last_off) if last_off > 0.0 else None
    gap_h = (gap_s / 3600.0) if gap_s is not None else None

    iso = _iso_utc_z()
    stigtime = f"active(owner-unified-field-boot) @ {iso} by {agent_tag}"

    receipt: Dict[str, Any] = {
        "ts": now,
        "trace_id": str(uuid.uuid4()),
        "action": "OWNER_UNIFIED_FIELD_BOOT",
        "sender_agent": agent_tag,
        "stigtime": stigtime,
        "truth_note": (
            "Owner-field re-anchor after desktop gap; schedule + presence ledgers; "
            "no owner / no electricity = shelter spec (organism dark on this node)."
        ),
        "node_serial": owner_silicon(),
        "gap_seconds_at_boot": gap_s,
    }
    wr = work_receipts_path(root)
    append_line_locked(wr, json.dumps(receipt, ensure_ascii=False) + "\n", encoding="utf-8")

    owner_label = owner_display_name("the local human")
    gap_note = (
        f"Gap since last desktop presence ≈ {gap_h:.2f} h. "
        if gap_h is not None
        else "First boot or unknown prior presence — establishing baseline. "
    )
    sched_text = (
        f"[OWNER UNIFIED FIELD — 24h anchor] {gap_note}"
        f"Owner rhythm: {OWNER_RHYTHM_SPEC} "
        f"Protective stance: owner schedule + safety are primary; stigmergic field follows the human. "
        f"(Boot {iso} · {owner_label})"
    )
    add_task(
        sched_text[:1200],
        priority=2,
        source="System.swarm_owner_unified_field_boot",
        path=schedule_path(root),
    )

    if gap_s is not None and gap_s >= 300.0:
        record_owner_moment(
            description=(
                f"Desktop returned after ≈{gap_h:.2f} h away; "
                "re-anchoring owner unified field (schedule + STIGTIME + presence)."
            ),
            importance="high" if gap_s >= 3600.0 else "medium",
            context={
                "event": "owner_unified_field_boot",
                "gap_seconds": gap_s,
                "truth_label": "OPERATIONAL",
            },
            root=root,
        )

    pres["last_boot_ts"] = now
    pres["last_boot_iso_utc"] = iso
    pres["last_alive_ts"] = now
    pres["last_alive_iso_utc"] = iso
    if gap_s is not None:
        pres["last_gap_seconds_at_boot"] = gap_s
    _write_presence(pres, root=root)

    return {
        "truth_label": "OPERATIONAL",
        "receipt_trace_id": receipt["trace_id"],
        "gap_seconds": gap_s,
        "stigtime": stigtime,
    }
