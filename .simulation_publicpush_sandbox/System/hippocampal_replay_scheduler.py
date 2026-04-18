#!/usr/bin/env python3
"""
hippocampal_replay_scheduler.py — Spaced replay scheduling for engram survival.
══════════════════════════════════════════════════════════════════════════════
Biology:
  Sharp-wave ripples / offline replay reactivate traces and bias consolidation.
  Buzsáki (1989): two-stage trace formation — online encoding vs offline replay.
  Eichenbaum (2004): hippocampal relational representations and declarative memory.
  Spaced repetition (Wozniak & Gorzelanczyk 1994): inter-repetition intervals expand
  with successful retrieval — modeled here via ease_factor and next_due_ts.

Function:
  1. DECAY MONITOR — natural forgetting curve + optional replay_bonus carryover.
  2. REPLAY QUEUE — persisted schedules; urgency-sorted execution batch.
  3. INTERVAL — SM-2–style ease_factor and multiplicative interval growth.
  4. REPLAY EXECUTOR — boosts replay_bonus (capped), logs JSONL, reschedules.
  5. ARCHITECT FLOOR — bonded / architect-tagged memories never sit below floor.

Hard contract:
  Does not rewrite arbitrary engram *content* blobs — only schedule metadata,
  replay_bonus, and JSONL events. Merge natural decay with replay_bonus each tick.

Biology anchors:
  Buzsáki, Neuroscience 31:551–570 (1989). DOI `10.1016/0306-4522(89)90423-5`
  Eichenbaum, Neuron 44:109–120 (2004). DOI `10.1016/j.neuron.2004.08.028`
  Wozniak & Gorzelanczyk, Acta Neurobiol Exp 54:59–62 (1994).
══════════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import json
import math
import sys
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.jsonl_file_lock import append_line_locked  # noqa: E402

_STATE = _REPO / ".sifta_state"
ENGRAM_LEDGER = _STATE / "hippocampal_engrams.json"  # persistent across sleep (optional)
ENGRAM_STORE_PFC = _STATE / "pfc_working_memory.json"
REPLAY_QUEUE = _STATE / "hippocampal_replay_queue.json"
REPLAY_LOG = _STATE / "hippocampal_replay_log.jsonl"
SCHEDULER_STATE = _STATE / "hippocampal_scheduler_state.json"
BOND_REGISTRY = _STATE / "oxytocin_bond_registry.json"
ARCHITECT_SOURCES_EXTRA = _STATE / "hippocampal_architect_sources.json"

REPLAY_THRESHOLD = 0.40
ARCHITECT_FLOOR = 0.55
REPLAY_BOOST = 0.35
RETENTION_CAP = 1.00
REPLAY_BONUS_HALF_LIFE_S = 86400.0 * 7.0  # replay lift fades over ~1 week if unreinforced

INITIAL_INTERVAL_S = 600.0
EASE_FACTOR_BASE = 1.8
EASE_FACTOR_MAX = 3.5
EASE_FACTOR_MIN = 1.3

STABILITY_BASE = 86400.0
ARCHITECT_STABILITY = 86400.0 * 7.0


class ReplayStatus(str, Enum):
    HEALTHY = "HEALTHY"
    SCHEDULED = "SCHEDULED"
    OVERDUE = "OVERDUE"
    REPLAYING = "REPLAYING"
    PROTECTED = "PROTECTED"


@dataclass
class EngramSchedule:
    engram_id: str
    source: str
    retention: float
    status: ReplayStatus
    ease_factor: float
    replay_count: int
    last_replay_ts: float
    next_due_ts: float
    interval_s: float
    consolidation_pri: int
    is_architect: bool
    replay_bonus: float = 0.0

    def urgency_score(self) -> float:
        overdue_factor = max(0.0, time.time() - self.next_due_ts) / 3600.0
        return self.retention - overdue_factor * 0.1

    def to_dict(self) -> dict:
        return {
            "engram_id": self.engram_id,
            "source": self.source,
            "retention": round(self.retention, 4),
            "status": self.status.value,
            "ease_factor": round(self.ease_factor, 4),
            "replay_count": self.replay_count,
            "last_replay_ts": self.last_replay_ts,
            "next_due_ts": self.next_due_ts,
            "interval_s": round(self.interval_s, 2),
            "consolidation_pri": self.consolidation_pri,
            "is_architect": self.is_architect,
            "replay_bonus": round(self.replay_bonus, 4),
        }


@dataclass
class ReplayReport:
    ts: float = field(default_factory=time.time)
    total_engrams: int = 0
    healthy: int = 0
    scheduled: int = 0
    overdue: int = 0
    protected: int = 0
    replayed: int = 0
    replayed_ids: List[str] = field(default_factory=list)
    dropped_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "ts": self.ts,
            "total_engrams": self.total_engrams,
            "healthy": self.healthy,
            "scheduled": self.scheduled,
            "overdue": self.overdue,
            "protected": self.protected,
            "replayed": self.replayed,
            "replayed_ids": self.replayed_ids,
            "dropped_ids": self.dropped_ids,
        }


def _decay_replay_bonus(bonus: float, dt: float) -> float:
    if bonus <= 0.0 or dt <= 0.0:
        return max(0.0, bonus)
    lam = math.log(2.0) / REPLAY_BONUS_HALF_LIFE_S
    return max(0.0, bonus * math.exp(-lam * dt))


class HippocampalReplayScheduler:
    """
    Call :meth:`tick` after Ebbinghaus-style salience updates (or on a cadence).
    Call :meth:`execute_replay_session` during sleep / low-load windows **before**
    glymphatic flush if you still need volatile PFC rows merged into this scan.
    """

    def __init__(self, state_root: Optional[Path] = None) -> None:
        self._root = Path(state_root) if state_root is not None else _STATE
        self._schedules: Dict[str, EngramSchedule] = self._load_schedules()
        self._architect_sources: Set[str] = self._load_architect_sources()
        self._last_tick_ts: float = self._load_scheduler_clock()

    # --- paths bound to root -------------------------------------------------
    def _p(self, name: str) -> Path:
        return self._root / name if self._root != _STATE else _STATE / name

    @property
    def _engram_ledger(self) -> Path:
        return self._root / "hippocampal_engrams.json" if self._root != _STATE else ENGRAM_LEDGER

    @property
    def _engram_pfc(self) -> Path:
        return self._root / "pfc_working_memory.json" if self._root != _STATE else ENGRAM_STORE_PFC

    @property
    def _replay_queue(self) -> Path:
        return self._root / "hippocampal_replay_queue.json" if self._root != _STATE else REPLAY_QUEUE

    @property
    def _replay_log(self) -> Path:
        return self._root / "hippocampal_replay_log.jsonl" if self._root != _STATE else REPLAY_LOG

    @property
    def _sched_state_path(self) -> Path:
        return self._root / "hippocampal_scheduler_state.json" if self._root != _STATE else SCHEDULER_STATE

    @property
    def _bond_registry(self) -> Path:
        return self._root / "oxytocin_bond_registry.json" if self._root != _STATE else BOND_REGISTRY

    @property
    def _architect_extra_path(self) -> Path:
        return self._root / "hippocampal_architect_sources.json" if self._root != _STATE else ARCHITECT_SOURCES_EXTRA

    # --- public API -----------------------------------------------------------

    def tick(self) -> ReplayReport:
        report = ReplayReport()
        now = time.time()
        dt = max(0.0, now - self._last_tick_ts)
        self._last_tick_ts = now
        self._persist_scheduler_clock()

        engrams = self._load_engrams()
        report.total_engrams = len(engrams)

        for eng in engrams:
            eid = str(eng.get("engram_id", eng.get("id", uuid.uuid4().hex)))
            source = str(eng.get("source", "UNKNOWN"))
            created = float(eng.get("created_ts", eng.get("timestamp", now)))
            pri = int(eng.get("consolidation_priority", eng.get("consolidation_pri", 1)))
            is_arch = bool(
                eng.get("is_architect", False)
                or source in self._architect_sources
                or source == "ARCHITECT"
            )

            natural = self._ebbinghaus_retention(created, pri, is_arch)
            sched = self._get_or_create_schedule(eid, source, pri, is_arch, natural)

            sched.replay_bonus = _decay_replay_bonus(sched.replay_bonus, dt)
            retention = min(RETENTION_CAP, natural + sched.replay_bonus)

            if is_arch and retention < ARCHITECT_FLOOR:
                sched.retention = ARCHITECT_FLOOR
                sched.status = ReplayStatus.PROTECTED
                sched.replay_bonus = max(sched.replay_bonus, ARCHITECT_FLOOR - natural)
                report.protected += 1
                self._schedules[eid] = sched
                continue

            sched.retention = retention

            if retention < REPLAY_THRESHOLD:
                if now > sched.next_due_ts:
                    sched.status = ReplayStatus.OVERDUE
                    report.overdue += 1
                else:
                    sched.status = ReplayStatus.SCHEDULED
                    report.scheduled += 1
            else:
                sched.status = ReplayStatus.HEALTHY
                report.healthy += 1

            self._schedules[eid] = sched

        self._persist_schedules()
        return report

    def execute_replay_session(self, max_replays: int = 10) -> ReplayReport:
        report = ReplayReport()
        pending = [
            s
            for s in self._schedules.values()
            if s.status in (ReplayStatus.SCHEDULED, ReplayStatus.OVERDUE)
        ]
        pending.sort(key=lambda s: s.urgency_score())

        for sched in pending[:max_replays]:
            sched.replay_bonus = min(RETENTION_CAP, sched.replay_bonus + REPLAY_BOOST)
            sched.retention = min(RETENTION_CAP, sched.retention + REPLAY_BOOST)
            sched.replay_count += 1
            sched.last_replay_ts = time.time()

            sched.ease_factor = min(
                EASE_FACTOR_MAX,
                max(
                    EASE_FACTOR_MIN,
                    sched.ease_factor + 0.1 * (sched.consolidation_pri - 2),
                ),
            )
            sched.interval_s = float(sched.interval_s * sched.ease_factor)
            sched.next_due_ts = time.time() + sched.interval_s
            sched.status = ReplayStatus.HEALTHY

            self._log_replay(sched)
            report.replayed_ids.append(sched.engram_id)
            report.replayed += 1

        self._persist_schedules()
        return report

    def register_architect_source(self, source: str) -> None:
        self._architect_sources.add(source)
        self._persist_architect_sources()

    def get_schedule(self, engram_id: str) -> Optional[EngramSchedule]:
        return self._schedules.get(engram_id)

    def overdue_count(self) -> int:
        return sum(1 for s in self._schedules.values() if s.status == ReplayStatus.OVERDUE)

    # --- Ebbinghaus -----------------------------------------------------------

    @staticmethod
    def _ebbinghaus_retention(
        created_ts: float,
        consolidation_pri: int,
        is_architect: bool,
    ) -> float:
        t = max(0.0, time.time() - created_ts)
        stability_mult = 1.0 + (consolidation_pri - 1) * 0.5
        base_s = ARCHITECT_STABILITY if is_architect else STABILITY_BASE
        s = base_s * stability_mult
        return float(math.exp(-t / s))

    # --- schedules ------------------------------------------------------------

    def _get_or_create_schedule(
        self,
        eid: str,
        source: str,
        pri: int,
        is_arch: bool,
        natural_retention: float,
    ) -> EngramSchedule:
        if eid in self._schedules:
            return self._schedules[eid]
        ease = min(EASE_FACTOR_MAX, EASE_FACTOR_BASE + (pri - 1) * 0.2)
        now = time.time()
        return EngramSchedule(
            engram_id=eid,
            source=source,
            retention=natural_retention,
            status=ReplayStatus.HEALTHY,
            ease_factor=ease,
            replay_count=0,
            last_replay_ts=now,
            next_due_ts=now + INITIAL_INTERVAL_S,
            interval_s=float(INITIAL_INTERVAL_S),
            consolidation_pri=pri,
            is_architect=is_arch,
            replay_bonus=0.0,
        )

    def _load_engrams(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []

        ledger_path = self._engram_ledger
        if ledger_path.exists():
            try:
                data = json.loads(ledger_path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    out.extend(data)
                else:
                    out.extend(data.get("engrams", []))
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                pass

        pfc = self._engram_pfc
        if pfc.exists():
            try:
                data = json.loads(pfc.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    out.extend(self._normalize_pfc_row(x, i) for i, x in enumerate(data))
                else:
                    if "engrams" in data:
                        out.extend(data["engrams"])
                    fused = data.get("fused_working_memory", [])
                    for i, row in enumerate(fused):
                        out.append(self._normalize_fused_engram(row, i))
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                pass

        seen: Set[str] = set()
        dedup: List[Dict[str, Any]] = []
        for row in out:
            eid = str(row.get("engram_id", row.get("id", "")))
            if not eid or eid in seen:
                continue
            seen.add(eid)
            dedup.append(row)
        return dedup

    @staticmethod
    def _normalize_fused_engram(row: Dict[str, Any], idx: int) -> Dict[str, Any]:
        ts = float(row.get("created_ts", row.get("timestamp", time.time())))
        base = dict(row)
        base.setdefault("engram_id", row.get("id", f"fused_{idx}_{int(ts)}"))
        base.setdefault("created_ts", ts)
        base.setdefault("source", row.get("source", "PFC_FUSED"))
        base.setdefault("consolidation_priority", int(row.get("consolidation_priority", 1)))
        if "synaptic_salience" in row:
            base.setdefault("consolidation_priority", max(1, int(round(float(row["synaptic_salience"]) * 5)) or 1))
        return base

    @staticmethod
    def _normalize_pfc_row(row: Any, idx: int) -> Dict[str, Any]:
        if isinstance(row, dict):
            return HippocampalReplayScheduler._normalize_fused_engram(row, idx)
        return {"engram_id": f"row_{idx}", "source": "UNKNOWN", "created_ts": time.time()}

    # --- persistence --------------------------------------------------------

    def _load_schedules(self) -> Dict[str, EngramSchedule]:
        path = self._replay_queue
        if not path.exists():
            return {}
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            result: Dict[str, EngramSchedule] = {}
            for eid, d in raw.items():
                result[eid] = EngramSchedule(
                    engram_id=d["engram_id"],
                    source=d["source"],
                    retention=float(d["retention"]),
                    status=ReplayStatus(d["status"]),
                    ease_factor=float(d["ease_factor"]),
                    replay_count=int(d["replay_count"]),
                    last_replay_ts=float(d["last_replay_ts"]),
                    next_due_ts=float(d["next_due_ts"]),
                    interval_s=float(d["interval_s"]),
                    consolidation_pri=int(d["consolidation_pri"]),
                    is_architect=bool(d["is_architect"]),
                    replay_bonus=float(d.get("replay_bonus", 0.0)),
                )
            return result
        except (OSError, json.JSONDecodeError, TypeError, ValueError, KeyError):
            return {}

    def _persist_schedules(self) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        path = self._replay_queue
        path.write_text(
            json.dumps({eid: s.to_dict() for eid, s in self._schedules.items()}, indent=2),
            encoding="utf-8",
        )

    def _load_scheduler_clock(self) -> float:
        p = self._sched_state_path
        if not p.exists():
            return time.time()
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            return float(d.get("last_tick_ts", time.time()))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return time.time()

    def _persist_scheduler_clock(self) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        self._sched_state_path.write_text(
            json.dumps({"last_tick_ts": self._last_tick_ts}, indent=2),
            encoding="utf-8",
        )

    def _load_architect_sources(self) -> Set[str]:
        base: Set[str] = {"ARCHITECT"}
        if self._bond_registry.exists():
            try:
                bonds = json.loads(self._bond_registry.read_text(encoding="utf-8"))
                base |= {s for s, v in bonds.items() if float(v) >= 0.70}
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                pass
        extra = self._architect_extra_path
        if extra.exists():
            try:
                arr = json.loads(extra.read_text(encoding="utf-8"))
                if isinstance(arr, list):
                    base |= {str(x) for x in arr}
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                pass
        return base

    def _persist_architect_sources(self) -> None:
        extra = sorted(self._architect_sources - {"ARCHITECT"})
        self._root.mkdir(parents=True, exist_ok=True)
        self._architect_extra_path.write_text(json.dumps(extra, indent=2), encoding="utf-8")

    def _log_replay(self, sched: EngramSchedule) -> None:
        row = {
            "engram_id": sched.engram_id,
            "source": sched.source,
            "replay_count": sched.replay_count,
            "retention_after": round(sched.retention, 4),
            "replay_bonus": round(sched.replay_bonus, 4),
            "next_interval_s": round(sched.interval_s, 2),
            "ts": time.time(),
        }
        self._root.mkdir(parents=True, exist_ok=True)
        append_line_locked(self._replay_log, json.dumps(row, ensure_ascii=False) + "\n")

    # --- smoke ----------------------------------------------------------------


def _smoke_save(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


if __name__ == "__main__":
    import tempfile

    tmp = Path(tempfile.mkdtemp(prefix="sifta_hippo_"))
    now = time.time()
    engrams = [
        {
            "engram_id": "eng_001",
            "source": "ARCHITECT",
            "created_ts": now - 120.0,
            "consolidation_priority": 5,
            "is_architect": True,
            "content_hash": "abc",
        },
        {
            "engram_id": "eng_002",
            "source": "CP2F",
            "created_ts": now - 3600.0,
            "consolidation_priority": 3,
            "is_architect": False,
            "content_hash": "def",
        },
        {
            "engram_id": "eng_003",
            "source": "AG31",
            "created_ts": now - 86400.0,
            "consolidation_priority": 2,
            "is_architect": False,
            "content_hash": "ghi",
        },
        {
            "engram_id": "eng_004",
            "source": "UNKNOWN",
            "created_ts": now - 86400.0 * 3.0,
            "consolidation_priority": 1,
            "is_architect": False,
            "content_hash": "jkl",
        },
        {
            "engram_id": "eng_005",
            "source": "ARCHITECT",
            "created_ts": now - 86400.0 * 5.0,
            "consolidation_priority": 5,
            "is_architect": True,
            "content_hash": "mno",
        },
    ]
    _smoke_save(tmp / "pfc_working_memory.json", {"engrams": engrams})

    scheduler = HippocampalReplayScheduler(state_root=tmp)
    scheduler.register_architect_source("ARCHITECT")

    print("=== HIPPOCAMPAL REPLAY SCHEDULER — SMOKE TEST (isolated tmp state) ===\n")
    print("--- TICK (decay scan) ---")
    report = scheduler.tick()
    print(
        f"  Total: {report.total_engrams}  Healthy: {report.healthy}  "
        f"Scheduled: {report.scheduled}  Overdue: {report.overdue}  Protected: {report.protected}\n"
    )

    icons = {
        ReplayStatus.HEALTHY: "[ok]",
        ReplayStatus.SCHEDULED: "[sched]",
        ReplayStatus.OVERDUE: "[due]",
        ReplayStatus.PROTECTED: "[prot]",
        ReplayStatus.REPLAYING: "[run]",
    }
    for eid, sched in scheduler._schedules.items():
        arch = " ARCHITECT" if sched.is_architect else ""
        print(
            f"  {icons.get(sched.status, '[?]')} [{sched.engram_id}]  "
            f"retention={sched.retention:.3f}  status={sched.status.value:<10}  "
            f"replays={sched.replay_count}  next_in={sched.interval_s/60:.1f}min{arch}"
        )
        print(f"             source={sched.source}  pri={sched.consolidation_pri}")

    print("\n--- REPLAY SESSION (sleep window) ---")
    replay_report = scheduler.execute_replay_session(max_replays=10)
    print(f"  Replayed: {replay_report.replayed}  IDs: {replay_report.replayed_ids}\n")

    print("--- POST-REPLAY (replayed rows) ---")
    for eid in replay_report.replayed_ids:
        s = scheduler._schedules.get(eid)
        if s:
            print(
                f"  [{eid}]  retention={s.retention:.3f}  "
                f"next_replay_in={s.interval_s/3600:.2f}hr  ease={s.ease_factor:.2f}"
            )

    print(f"\nOverdue count after replay: {scheduler.overdue_count()}")
    print(f"(tmp state: {tmp})")
