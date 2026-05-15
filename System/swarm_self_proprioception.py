#!/usr/bin/env python3
"""
swarm_self_proprioception.py — Inward swarm substrate snapshot (OBSERVED)

Reads ledgers / kernel snapshot only. No imperatives to the caller, no learner
mutation. Default ``read()`` is side-effect-free (silent sensor). Extend with
explicit receipt logging only behind a deliberate caller-side gate.

Distinct from swarm_proprioception.SwarmProprioception (host pmset/storage).
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.swarm_kernel_identity import owner_silicon

try:
    from System.swarm_kernel_process_table import (
        DEFAULT_STATE_ROOT as _KERNEL_DEFAULT_ROOT,
        get_kernel_process_table,
    )
except Exception:  # pragma: no cover - import guarded for minimal smoke contexts
    get_kernel_process_table = None  # type: ignore[misc, assignment]
    _KERNEL_DEFAULT_ROOT = _REPO / ".sifta_state"

try:
    from System.stgm_economy import scan_economy
except Exception:  # pragma: no cover
    scan_economy = None  # type: ignore[misc, assignment]

_MAX_TAIL_BYTES = 256_000


def _tail_text(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        size = path.stat().st_size
    except OSError:
        return ""
    try:
        with path.open("rb") as f:
            if size <= _MAX_TAIL_BYTES:
                raw = f.read()
            else:
                f.seek(size - _MAX_TAIL_BYTES)
                raw = f.read()
        return raw.decode("utf-8", errors="replace")
    except OSError:
        return ""


def _tail_json_objects(path: Path, n: int) -> List[Dict[str, Any]]:
    if n <= 0:
        return []
    text = _tail_text(path)
    out: List[Dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out[-n:]


class SwarmSelfProprioception:
    """Minimal inward-facing sense organ — structured JSON snapshot only."""

    truth_label = "SELF_PROPRIOCEPTION_V1"

    def __init__(self, state_root: Optional[Path | str] = None) -> None:
        self.state_dir = Path(state_root or _KERNEL_DEFAULT_ROOT)
        self.kernel_snap = self.state_dir / "kernel_process_table.json"
        self.kernel_ledger = self.state_dir / "kernel_process_table.jsonl"
        self.visual = self.state_dir / "visual_stigmergy.jsonl"
        self.face = self.state_dir / "face_detection_events.jsonl"
        self.burn = self.state_dir / "organ_burn.jsonl"
        self.owner = self.state_dir / "owner_genesis.json"
        self.last_frame = self.state_dir / "visual_stigmergy_last_frame.jpg"

    def read(self) -> Dict[str, Any]:
        """Return current substrate hints. No ledger writes."""
        now = time.time()
        snap: Dict[str, Any] = {
            "truth_label": self.truth_label,
            "t": round(now, 3),
            "homeworld_serial": owner_silicon(),
            "kernel": self._kernel_summary(),
            "last_visual_wake": self._last_visual_wake(),
            "last_face_event_age_s": self._face_age_s(now),
            "last_photo_frame_age_s": self._photo_frame_age_s(now),
            "stgm_wallet": self._wallet(),
            "recent_organ_burn": _tail_json_objects(self.burn, 5),
            "owner_bound": self._owner_bound(),
            "field_hints": {"state_dir": str(self.state_dir.resolve())},
            "sensor_completeness": 0.0,
        }
        snap["sensor_completeness"] = round(
            self._completeness(snap),
            3,
        )
        return snap

    def _completeness(self, snap: Dict[str, Any]) -> float:
        keys = ("kernel", "last_visual_wake", "stgm_wallet", "owner_bound")
        hits = sum(1 for k in keys if bool(snap.get(k)))
        if snap.get("last_face_event_age_s") is not None:
            hits += 1
        if snap.get("last_photo_frame_age_s") is not None:
            hits += 1
        return hits / float(len(keys) + 2)

    def _kernel_summary(self) -> Dict[str, Any]:
        if get_kernel_process_table is not None:
            try:
                table = get_kernel_process_table(state_root=self.state_dir)
                s = table.snapshot()
                procs = s.get("processes") or {}
                alive = [
                    pid
                    for pid, row in procs.items()
                    if isinstance(row, dict) and str(row.get("status") or "") == "alive"
                ]
                return {
                    "source": "KernelProcessTable.snapshot",
                    "process_count": int(s.get("process_count") or 0),
                    "aggregate_health": float(s.get("aggregate_health") or 0.0),
                    "alive_count": len(alive),
                    "alive_preview": alive[:24],
                    "truth_label": str(s.get("truth_label") or ""),
                }
            except Exception:
                pass
        if self.kernel_snap.exists():
            try:
                data = json.loads(self.kernel_snap.read_text(encoding="utf-8", errors="replace"))
                if isinstance(data, dict):
                    pc = len(data.get("processes") or {}) if isinstance(data.get("processes"), dict) else 0
                    return {"source": "kernel_process_table.json", "process_count": pc}
            except Exception:
                pass
        tail = _tail_json_objects(self.kernel_ledger, 1)
        if tail:
            return {"source": "kernel_process_table.jsonl_tail", "last_row_kind": tail[-1].get("kind")}
        return {"source": "UNKNOWN", "reason": "no_kernel_snapshot"}

    def _last_visual_wake(self) -> Optional[Dict[str, Any]]:
        rows = _tail_json_objects(self.visual, 32)
        for row in reversed(rows):
            wr = row.get("wake_reason")
            if wr is not None:
                ts = row.get("t") or row.get("ts")
                return {
                    "wake_reason": wr,
                    "t": ts,
                    "schedule_ms": row.get("schedule_ms"),
                    "delta": row.get("delta"),
                    "source": row.get("source"),
                }
        return None

    def _face_age_s(self, now: float) -> Optional[float]:
        rows = _tail_json_objects(self.face, 3)
        if not rows:
            return None
        ts = rows[-1].get("ts")
        if isinstance(ts, (int, float)) and ts > 0:
            return round(max(0.0, now - float(ts)), 3)
        return None

    def _photo_frame_age_s(self, now: float) -> Optional[float]:
        if not self.last_frame.exists():
            return None
        try:
            m = self.last_frame.stat().st_mtime
            return round(max(0.0, now - m), 3)
        except OSError:
            return None

    def _wallet(self) -> Dict[str, Any]:
        if scan_economy is None:
            return {"canonical_wallet_sum_stgm": None, "reason": "scan_unavailable"}
        try:
            snap = scan_economy(state_dir=self.state_dir)
            return {
                "canonical_wallet_sum_stgm": round(float(snap.canonical_wallet_sum), 4),
                "warnings": list(snap.warnings or [])[:4],
            }
        except Exception as exc:
            return {"canonical_wallet_sum_stgm": None, "reason": type(exc).__name__}

    def _owner_bound(self) -> Dict[str, Any]:
        bound: Dict[str, Any] = {
            "owner_genesis_present": self.owner.exists(),
        }
        if self.owner.exists():
            try:
                og = json.loads(self.owner.read_text(encoding="utf-8", errors="replace"))
                if isinstance(og, dict):
                    if "GENESIS_ANCHOR" in og:
                        ah = str(og.get("GENESIS_ANCHOR") or "")
                        bound["genesis_anchor_prefix"] = ah[:16] + ("…" if len(ah) > 16 else "")
            except Exception:
                bound["read_error"] = True
        try:
            from System.swarm_kernel_identity import owner_display_name

            bound["owner_display"] = owner_display_name()
        except Exception:
            pass
        return bound


def snapshot(state_root: Optional[Path | str] = None) -> Dict[str, Any]:
    """Convenience: one-shot read for swimmers / tooling."""
    return SwarmSelfProprioception(state_root=state_root).read()
