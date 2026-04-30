#!/usr/bin/env python3
"""
System/whatsapp_autonomy_settings.py
Per-contact/per-group owner delegation for Alice's WhatsApp autonomy.

Default is OFF. A target becomes eligible for autonomous replies only after
George enables it in the WhatsApp Organ. This is standing owner delegation,
not blanket permission: every outgoing message still goes through the normal
WhatsApp effector receipt path.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_SETTINGS_FILE = _STATE / "whatsapp_autonomy_settings.json"
_SETTINGS_LEDGER = _STATE / "whatsapp_autonomy_settings.jsonl"

SCHEMA = "SIFTA_WHATSAPP_AUTONOMY_SETTINGS_V1"


def _chat_type_for(jid: str, chat_type: str = "") -> str:
    chat_type = str(chat_type or "").strip().lower()
    if chat_type in {"direct", "group"}:
        return chat_type
    return "group" if str(jid or "").strip().endswith("@g.us") else "direct"


def _target_key(jid: str) -> str:
    return str(jid or "").strip()


def load_settings(path: Optional[Path] = None) -> Dict[str, Any]:
    path = _SETTINGS_FILE if path is None else path
    if not path.exists():
        return {"schema": SCHEMA, "targets": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"schema": SCHEMA, "targets": {}}
        targets = data.get("targets")
        if not isinstance(targets, dict):
            data["targets"] = {}
        data["schema"] = SCHEMA
        return data
    except Exception:
        return {"schema": SCHEMA, "targets": {}}


def _write_settings(data: Dict[str, Any], path: Optional[Path] = None) -> None:
    path = _SETTINGS_FILE if path is None else path
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def _append_receipt(row: Dict[str, Any], ledger_path: Optional[Path] = None) -> None:
    ledger_path = _SETTINGS_LEDGER if ledger_path is None else ledger_path
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        from System.jsonl_file_lock import append_line_locked

        append_line_locked(ledger_path, json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        with ledger_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _owner_or_control_target(jid: str, display_name: str = "") -> bool:
    try:
        from System.whatsapp_social_graph import (
            LOCAL_CONTROL_JIDS,
            OWNER_NAME_ALIASES,
            OWNER_SELF_JIDS,
        )

        name = " ".join(str(display_name or "").casefold().split())
        return jid in OWNER_SELF_JIDS or jid in LOCAL_CONTROL_JIDS or name in OWNER_NAME_ALIASES
    except Exception:
        return False


def set_auto_enabled(
    jid: str,
    *,
    display_name: str = "",
    chat_type: str = "",
    enabled: bool,
    actor: str = "owner",
    source: str = "whatsapp_organ",
    path: Optional[Path] = None,
    ledger_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Set owner-delegated auto-reply for one WhatsApp JID/group."""
    jid = _target_key(jid)
    if not jid:
        raise ValueError("jid is required")
    chat_type = _chat_type_for(jid, chat_type)
    display_name = str(display_name or "").strip()
    if enabled and _owner_or_control_target(jid, display_name):
        raise ValueError("owner_self_or_control_channel_cannot_enable_auto_reply")

    data = load_settings(path)
    targets = data.setdefault("targets", {})
    now = time.time()
    row = dict(targets.get(jid) or {})
    row.update(
        {
            "jid": jid,
            "display_name": display_name,
            "chat_type": chat_type,
            "auto_reply_enabled": bool(enabled),
            "consent": "owner_delegated" if enabled else "revoked",
            "source": source,
            "actor": actor,
            "updated_ts": now,
        }
    )
    targets[jid] = row
    data["schema"] = SCHEMA
    data["updated_ts"] = now
    _write_settings(data, path)

    receipt = {
        "event_kind": "WHATSAPP_AUTO_REPLY_SETTING_CHANGED",
        "schema": SCHEMA,
        "ts": now,
        "jid": jid,
        "display_name": display_name,
        "chat_type": chat_type,
        "auto_reply_enabled": bool(enabled),
        "consent": row["consent"],
        "actor": actor,
        "source": source,
        "truth_note": "Owner-delegated standing consent for this target only; every send still needs an effector receipt.",
        "ok": True,
    }
    _append_receipt(receipt, ledger_path)
    return row


def is_auto_enabled(
    jid: str,
    *,
    chat_type: str = "",
    settings: Optional[Dict[str, Any]] = None,
    path: Optional[Path] = None,
) -> bool:
    jid = _target_key(jid)
    if not jid:
        return False
    data = load_settings(path) if settings is None else settings
    row = (data.get("targets") or {}).get(jid) or {}
    if not bool(row.get("auto_reply_enabled")):
        return False
    if _chat_type_for(jid, chat_type) != _chat_type_for(jid, str(row.get("chat_type") or "")):
        return False
    return str(row.get("consent") or "") == "owner_delegated"


def target_policy(jid: str, *, chat_type: str = "", path: Optional[Path] = None) -> Dict[str, Any]:
    data = load_settings(path)
    row = dict((data.get("targets") or {}).get(_target_key(jid)) or {})
    row.setdefault("jid", _target_key(jid))
    row.setdefault("chat_type", _chat_type_for(jid, chat_type))
    row.setdefault("auto_reply_enabled", False)
    row.setdefault("consent", "none")
    return row


def summary_for_alice(limit: int = 8) -> str:
    data = load_settings()
    enabled = [
        row
        for row in (data.get("targets") or {}).values()
        if isinstance(row, dict) and row.get("auto_reply_enabled")
    ]
    enabled.sort(key=lambda row: float(row.get("updated_ts") or 0.0), reverse=True)
    lines = [
        "WHATSAPP AUTO-REPLY TARGETS:",
        "- Default=OFF. Alice may auto-answer only targets George toggled ON in the WhatsApp Organ.",
    ]
    if not enabled:
        lines.append("- enabled_targets=0")
        return "\n".join(lines)
    visible = []
    for row in enabled[:limit]:
        label = str(row.get("display_name") or row.get("jid") or "?")
        visible.append(f"{label} ({row.get('chat_type')}, consent=owner_delegated)")
    lines.append("- enabled_targets=" + "; ".join(visible))
    return "\n".join(lines)


__all__ = [
    "SCHEMA",
    "is_auto_enabled",
    "load_settings",
    "set_auto_enabled",
    "summary_for_alice",
    "target_policy",
]
