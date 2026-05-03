"""
Event 120/121 — Circadian Agent Lobe (60s polite environmental watcher).

Covenant posture: **read-heavy, receipt-driven**. Appends locked JSONL only.
Does not spawn model subprocesses or mutate repo by default — that stays
behind explicit future GO + allowlists.

Complements Event 119 owner unified field (`owner_desktop_presence.json`) by
sampling machine + presence proxies on a human-scale cadence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import psutil as _psutil
except Exception:  # pragma: no cover
    _psutil = None

from System.jsonl_file_lock import append_line_locked, read_text_locked
from System.swarm_kernel_identity import owner_silicon

try:
    from System.swarm_owner_unified_field_boot import presence_path as _presence_path
except Exception:  # pragma: no cover - fallback is used on clean checkouts.
    _presence_path = None

try:
    from System.swarm_persistent_owner_history import state_dir as _owner_state_dir
except Exception:  # pragma: no cover - fallback is used on clean checkouts.
    _owner_state_dir = None

AGENDA_NAME = "circadian_agenda.jsonl"
HEARTBEAT_NAME = "owner_heartbeat.jsonl"
LEGACY_HEARTBEAT_NAME = "circadian_lobe_heartbeat.jsonl"
TRUTH_HEARTBEAT = "CIRCADIAN_OWNER_HEARTBEAT_120"
TRUTH_AGENDA = "CIRCADIAN_AGENDA_ITEM_120"
TRUTH_SUMMARY = "CIRCADIAN_AGENT_SUMMARY_120"
WATCHER_PERIOD_S = 60


def state_dir(root: Optional[Path] = None) -> Path:
    if _owner_state_dir is not None:
        return _owner_state_dir(root)
    if root is not None:
        return Path(root)
    return Path(__file__).resolve().parents[1] / ".sifta_state"


def presence_path(root: Optional[Path] = None) -> Path:
    if _presence_path is not None:
        return _presence_path(root)
    return state_dir(root) / "owner_desktop_presence.json"


def agenda_path(root: Optional[Path] = None) -> Path:
    return state_dir(root) / AGENDA_NAME


def heartbeat_path(root: Optional[Path] = None) -> Path:
    return state_dir(root) / HEARTBEAT_NAME


def _memory_percent() -> float:
    if _psutil is not None:
        try:
            return round(float(_psutil.virtual_memory().percent), 1)
        except Exception:
            pass
    try:
        total_bytes = int(
            subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True).strip()
        )
        vm = subprocess.check_output(["vm_stat"], stderr=subprocess.DEVNULL, text=True)
        page_size = 4096
        m = re.search(r"page size of (\d+) bytes", vm)
        if m:
            page_size = int(m.group(1))
        free_pages = 0
        for label in ("Pages free", "Pages speculative"):
            mm = re.search(rf"{label}:\s+(\d+)\.", vm)
            if mm:
                free_pages += int(mm.group(1))
        used_bytes = max(0, total_bytes - free_pages * page_size)
        return round(min(100.0, used_bytes / max(1, total_bytes) * 100.0), 1)
    except Exception:
        return 0.0


def _cpu_signal() -> tuple[float, Optional[float]]:
    """Returns (cpu_or_load_metric, None) or (0, load1) when only loadavg."""
    if _psutil is not None:
        try:
            return round(float(_psutil.cpu_percent(interval=0.05)), 1), None
        except Exception:
            pass
    try:
        one, _, _ = os.getloadavg()
        return round(min(100.0, one * 25.0), 1), round(one, 2)
    except (OSError, AttributeError):
        return 0.0, None


def _ide_like_process_count() -> int:
    if _psutil is None:
        return -1
    needles = ("cursor", "code", "sifta", "antigravity", "pycharm", "electron")
    n = 0
    for p in _psutil.process_iter(["name"]):
        try:
            name = (p.info.get("name") or "").lower()
        except Exception:
            continue
        if any(x in name for x in needles):
            n += 1
    return n


def _owner_desktop_alive_age_sec(root: Optional[Path] = None) -> Optional[float]:
    p = presence_path(root)
    if not p.exists():
        return None
    try:
        raw = read_text_locked(p, encoding="utf-8")
        if not raw.strip():
            return None
        data = json.loads(raw)
        ts = data.get("last_alive_ts")
        if ts is None:
            return None
        return max(0.0, time.time() - float(ts))
    except Exception:
        return None


def _phase_for(ts: float) -> str:
    hour = datetime.fromtimestamp(ts).hour
    if hour < 5:
        return "night_repair"
    if hour < 11:
        return "morning_boot"
    if hour < 17:
        return "day_work"
    if hour < 22:
        return "evening_consolidation"
    return "late_rest"


def _heartbeat_id(row: Dict[str, Any]) -> str:
    payload = {
        "ts": row.get("ts"),
        "cpu_percent": row.get("cpu_percent"),
        "memory_percent": row.get("memory_percent"),
        "ide_like_processes": row.get("ide_like_processes"),
        "owner_desktop_alive_age_sec": row.get("owner_desktop_alive_age_sec"),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:12]


def collect_environment_snapshot(root: Optional[Path] = None, *, now: Optional[float] = None) -> Dict[str, Any]:
    ts = time.time() if now is None else float(now)
    mem = _memory_percent()
    cpu, load1 = _cpu_signal()
    ide_n = _ide_like_process_count()
    alive_age = _owner_desktop_alive_age_sec(root)
    disk_pct: Optional[float] = None
    try:
        if _psutil is not None:
            disk_pct = round(float(_psutil.disk_usage("/").percent), 1)
        else:
            usage = shutil.disk_usage("/")
            disk_pct = round(usage.used / max(1, usage.total) * 100.0, 1)
    except Exception:
        pass

    human = False
    if alive_age is not None and alive_age <= 1200.0:
        human = True
    if ide_n > 0:
        human = True
    if cpu >= 18.0:
        human = True

    signals: List[str] = []
    if alive_age is not None and alive_age <= 1200.0:
        signals.append("owner_desktop_presence_recent")
    if ide_n > 0:
        signals.append("ide_process_active")
    if cpu >= 18.0:
        signals.append("machine_load_active")

    row = {
        "ts": ts,
        "timestamp": ts,
        "local_iso": datetime.fromtimestamp(ts).isoformat(timespec="seconds"),
        "local_date": datetime.fromtimestamp(ts).date().isoformat(),
        "trace_id": str(uuid.uuid4()),
        "kind": "CIRCADIAN_HEARTBEAT",
        "node_serial": owner_silicon(),
        "watcher_period_s": WATCHER_PERIOD_S,
        "circadian_phase": _phase_for(ts),
        "cpu_percent": cpu,
        "load1": load1,
        "memory_percent": mem,
        "disk_percent": disk_pct,
        "ide_like_processes": ide_n,
        "active_ide_indicators": max(0, ide_n),
        "owner_desktop_alive_age_sec": alive_age,
        "human_likely_present": human,
        "presence_signals": signals,
        "psutil_available": _psutil is not None,
        "truth_label": TRUTH_HEARTBEAT,
        "safety_policy": "read_only_no_destructive_actions_without_explicit_go",
    }
    row["heartbeat_id"] = _heartbeat_id(row)
    return row


def append_heartbeat(root: Optional[Path] = None, *, now: Optional[float] = None) -> Dict[str, Any]:
    row = collect_environment_snapshot(root, now=now)
    append_line_locked(
        heartbeat_path(root),
        json.dumps(row, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return row


def add_agenda_item(
    task: str,
    *,
    priority: str = "medium",
    trigger_condition: str = "",
    status: str = "pending",
    root: Optional[Path] = None,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    task = " ".join(str(task or "").split())
    if not task:
        raise ValueError("agenda task cannot be empty")
    priority = str(priority or "medium").lower()
    if priority not in ("low", "medium", "high", "critical"):
        priority = "medium"
    ts = time.time() if now is None else float(now)
    dt = datetime.fromtimestamp(ts)
    item: Dict[str, Any] = {
        "date": dt.date().isoformat(),
        "ts": ts,
        "timestamp": ts,
        "local_iso": dt.isoformat(timespec="seconds"),
        "trace_id": str(uuid.uuid4()),
        "task": task,
        "priority": priority,
        "status": status,
        "truth_label": TRUTH_AGENDA,
        "safety_policy": "agenda_receipt_only_no_action_taken",
    }
    if trigger_condition:
        item["trigger_condition"] = trigger_condition
    append_line_locked(
        agenda_path(root),
        json.dumps(item, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return item


def read_agenda_for_date(
    day_iso: Optional[str] = None,
    *,
    root: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    path = agenda_path(root)
    if not path.exists():
        return []
    day = day_iso or datetime.now().date().isoformat()
    out: List[Dict[str, Any]] = []
    raw = read_text_locked(path, encoding="utf-8")
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("date") == day:
            out.append(obj)
    return out


def count_pending_agenda(root: Optional[Path] = None) -> int:
    n = 0
    raw = read_text_locked(agenda_path(root), encoding="utf-8")
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if str(obj.get("status", "pending")).lower() == "pending":
            n += 1
    return n


def run_circadian_pulse(root: Optional[Path] = None, *, now: Optional[float] = None) -> Dict[str, Any]:
    """One 60s-tick receipt: heartbeat + lightweight agenda stats (no task execution)."""
    hb = append_heartbeat(root, now=now)
    hb["pending_agenda_count"] = count_pending_agenda(root)
    return hb


def run_daemon_loop(
    interval_sec: float = 60.0,
    *,
    root: Optional[Path] = None,
    max_ticks: Optional[int] = None,
) -> None:
    """Long-running polite watcher. Stops after max_ticks if set (tests)."""
    tick = 0
    while max_ticks is None or tick < max_ticks:
        run_circadian_pulse(root)
        tick += 1
        # Floor 0.1s so tests can tick quickly; production uses env/default (e.g. 60).
        time.sleep(max(float(interval_sec), 0.1))


def get_system_heartbeat(*, state_dir: Optional[Path] = None, now: Optional[float] = None) -> Dict[str, Any]:
    return collect_environment_snapshot(state_dir, now=now)


def log_heartbeat(*, state_dir: Optional[Path] = None, now: Optional[float] = None) -> Dict[str, Any]:
    return append_heartbeat(state_dir, now=now)


def get_today_agenda(*, state_dir: Optional[Path] = None, now: Optional[float] = None) -> List[Dict[str, Any]]:
    day = datetime.fromtimestamp(float(now)).date().isoformat() if now is not None else None
    return read_agenda_for_date(day, root=state_dir)


def get_circadian_summary(*, state_dir: Optional[Path] = None, now: Optional[float] = None) -> Dict[str, Any]:
    ts = time.time() if now is None else float(now)
    latest = None
    for line in read_text_locked(heartbeat_path(state_dir), encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            latest = row
    agenda = get_today_agenda(state_dir=state_dir, now=ts)
    pending = [row for row in agenda if str(row.get("status", "pending")).lower() == "pending"]
    age_s = None
    if latest and isinstance(latest.get("ts"), (int, float)):
        age_s = max(0.0, round(ts - float(latest["ts"]), 3))
    return {
        "ts": ts,
        "truth_label": TRUTH_SUMMARY,
        "latest_heartbeat": latest,
        "heartbeat_age_s": age_s,
        "today_agenda_count": len(agenda),
        "pending_agenda_count": len(pending),
        "pending_agenda": pending[-5:],
        "watcher_period_s": WATCHER_PERIOD_S,
    }


def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Circadian Agent Lobe — receipt watcher")
    p.add_argument(
        "--loop",
        action="store_true",
        help="Run forever (interval from env or 60s)",
    )
    p.add_argument(
        "--interval",
        type=float,
        default=float(os.environ.get("SIFTA_CIRCADIAN_INTERVAL_SEC", "60")),
        help="Seconds between ticks when --loop",
    )
    p.add_argument(
        "--max-ticks",
        type=int,
        default=0,
        help="If >0 with --loop, exit after N ticks (debug/tests)",
    )
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = _parse_args(argv)
    if args.loop:
        run_daemon_loop(
            interval_sec=args.interval,
            max_ticks=args.max_ticks if args.max_ticks > 0 else None,
        )
        return 0
    row = run_circadian_pulse()
    print(json.dumps(row, indent=2, ensure_ascii=False))
    return 0


class CircadianAgentLobe:
    """Namespace shim for callers that prefer a class surface."""

    collect_environment_snapshot = staticmethod(collect_environment_snapshot)
    append_heartbeat = staticmethod(append_heartbeat)
    get_system_heartbeat = staticmethod(get_system_heartbeat)
    log_heartbeat = staticmethod(log_heartbeat)
    add_agenda_item = staticmethod(add_agenda_item)
    run_pulse = staticmethod(run_circadian_pulse)
    get_circadian_summary = staticmethod(get_circadian_summary)

    @staticmethod
    def get_today_agenda(
        root: Optional[Path] = None,
        *,
        state_dir: Optional[Path] = None,
        now: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        return get_today_agenda(state_dir=state_dir if state_dir is not None else root, now=now)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
