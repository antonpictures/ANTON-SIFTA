"""
Event 119 — Persistent owner life ledger (human continuity substrate).

Doctrine (Swarm): power cycles erase RAM and volatile context; the *trajectory*
of co-presence with the owner is the high-value signal. This module is a thin
append-only ledger + small manifest for boot-time summaries — not a full
hippocampus, not RLHS; it sits as a **continuity layer** between episodic logs
and the agent loop.

Identity: owner name and node serial come from `swarm_kernel_identity` /
`owner_genesis` — no hardcoded owner strings in species code.

Truth label: **OPERATIONAL** — JSON persistence only; not Ed25519 financial seals.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from System.jsonl_file_lock import append_line_locked, read_text_locked, rewrite_text_locked
from System.swarm_kernel_identity import owner_display_name, owner_name, owner_silicon


def state_dir(explicit: Optional[Path] = None) -> Path:
    if explicit is not None:
        return explicit
    env = os.environ.get("SIFTA_STATE_DIR")
    if env:
        return Path(env).expanduser()
    return Path(__file__).resolve().parent.parent / ".sifta_state"


def owner_history_log(root: Optional[Path] = None) -> Path:
    return state_dir(root) / "owner_life_history.jsonl"


def owner_manifest_path(root: Optional[Path] = None) -> Path:
    return state_dir(root) / "owner_manifest.json"


def _default_manifest(root: Optional[Path] = None) -> Dict[str, Any]:
    return {
        "owner_name": owner_name(),
        "node_serial": owner_silicon(),
        "first_contact": time.time(),
        "total_interaction_seconds": 0.0,
        "key_moments": [],
        "continuity_note": (
            "Trajectory over time matters more than raw log volume; "
            "rehydrate summaries on boot, do not confuse persistence with biology."
        ),
    }


def get_owner_manifest(root: Optional[Path] = None) -> Dict[str, Any]:
    path = owner_manifest_path(root)
    if not path.exists():
        return _default_manifest(root)
    try:
        raw = read_text_locked(path, encoding="utf-8")
        data = json.loads(raw) if raw.strip() else {}
        if not isinstance(data, dict):
            return _default_manifest(root)
        base = _default_manifest(root)
        base.update(data)
        return base
    except (json.JSONDecodeError, OSError):
        return _default_manifest(root)


def update_owner_manifest(update: Dict[str, Any], root: Optional[Path] = None) -> None:
    manifest = get_owner_manifest(root)
    manifest.update(update)
    manifest["last_update"] = time.time()
    manifest["owner_name"] = owner_name()
    manifest["node_serial"] = owner_silicon()
    path = owner_manifest_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    rewrite_text_locked(path, json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")


def record_owner_moment(
    description: str,
    importance: str = "medium",
    context: Optional[Dict[str, Any]] = None,
    *,
    interaction_seconds: float = 0.0,
    root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Append one human–owner life moment (append-only JSONL)."""
    owner = owner_name()
    moment = {
        "moment_id": uuid.uuid4().hex[:16],
        "timestamp": time.time(),
        "description": description,
        "importance": importance,
        "context": context or {},
        "human_owner": owner,
        "node_serial": owner_silicon(),
    }
    log = owner_history_log(root)
    line = json.dumps(moment, ensure_ascii=False) + "\n"
    append_line_locked(log, line, encoding="utf-8")

    manifest = get_owner_manifest(root)
    manifest["owner_name"] = owner
    manifest["node_serial"] = owner_silicon()
    prev = float(manifest.get("total_interaction_seconds") or 0.0)
    manifest["total_interaction_seconds"] = prev + max(0.0, interaction_seconds)
    if importance == "existential":
        keys = list(manifest.get("key_moments") or [])
        keys.append(moment["moment_id"])
        manifest["key_moments"] = keys[-256:]
    update_owner_manifest(manifest, root=root)
    return moment


def get_owner_life_summary(
    tail_moments: int = 10,
    root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Compact bundle for dashboards or prompt rehydration."""
    manifest = get_owner_manifest(root)
    moments: List[Dict[str, Any]] = []
    log = owner_history_log(root)
    if log.exists():
        text = read_text_locked(log, encoding="utf-8", errors="replace")
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                moments.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    tail = moments[-tail_moments:] if moments else []
    label = owner_display_name("the local human")
    return {
        "owner": manifest.get("owner_name", owner_name()),
        "owner_display": label,
        "total_moments_logged": len(moments),
        "key_moments_count": len(manifest.get("key_moments") or []),
        "last_moment": tail[-1] if tail else None,
        "recent_moments": tail,
        "continuity_status": "PERSISTENT_LEDGER — reboot does not delete JSONL on disk",
        "node_serial": manifest.get("node_serial", owner_silicon()),
    }


class PersistentOwnerHistory:
    """Namespace shim matching Architect-facing call style."""

    get_owner_manifest = staticmethod(get_owner_manifest)
    update_owner_manifest = staticmethod(update_owner_manifest)
    record_owner_moment = staticmethod(record_owner_moment)
    get_owner_life_summary = staticmethod(get_owner_life_summary)


if __name__ == "__main__":
    m = PersistentOwnerHistory.record_owner_moment(
        description="Architect noted concern about owner-history continuity across power cycles.",
        importance="existential",
        context={"emotion": "care", "truth_label": "OPERATIONAL"},
        interaction_seconds=0.0,
    )
    print(json.dumps({"recorded": m["moment_id"], "summary": get_owner_life_summary()}, indent=2))
