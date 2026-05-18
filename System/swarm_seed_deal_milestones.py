#!/usr/bin/env python3
"""Seed-deal milestone swimmers.

This organ turns the closed seed-deal receipt into a small stigmergic
posterior. Each commitment is represented by one fresh swimmer per
evaluation. The swimmer reads append-only local evidence ledgers, scores
matches, and reports a bounded posterior over ON_TRACK / AT_RISK /
COMPLETE. It never imports another node's private state and never
rewrites history.

Truth label: ``SIFTA_SEED_DEAL_MILESTONES_V1``.
"""
from __future__ import annotations

import json
import math
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_POSTERIOR_LEDGER = _STATE / "seed_deal_milestone_posteriors.jsonl"

_TRUTH_LABEL = "SIFTA_SEED_DEAL_MILESTONES_V1"


@dataclass(frozen=True)
class SeedMilestone:
    milestone_id: str
    title: str
    due_date: Optional[str]
    keyword_groups: Tuple[Tuple[str, ...], ...]
    commitment: str


@dataclass(frozen=True)
class MilestoneSwimmer:
    swimmer_id: str
    milestone_id: str
    title: str
    due_date: Optional[str]
    days_left: Optional[float]
    evidence_hits: int
    evidence_refs: Tuple[str, ...]
    complete_p: float
    on_track_p: float
    at_risk_p: float
    status: str

    def as_dict(self) -> Dict[str, Any]:
        return {
            "swimmer_id": self.swimmer_id,
            "milestone_id": self.milestone_id,
            "title": self.title,
            "due_date": self.due_date,
            "days_left": None if self.days_left is None else round(self.days_left, 2),
            "evidence_hits": self.evidence_hits,
            "evidence_refs": list(self.evidence_refs),
            "complete_p": round(self.complete_p, 3),
            "on_track_p": round(self.on_track_p, 3),
            "at_risk_p": round(self.at_risk_p, 3),
            "status": self.status,
        }


@dataclass(frozen=True)
class SeedDealPosterior:
    posterior_id: str
    ts: float
    truth_label: str
    swimmers: Tuple[MilestoneSwimmer, ...]
    summary: Dict[str, int]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "posterior_id": self.posterior_id,
            "ts": self.ts,
            "truth_label": self.truth_label,
            "summary": dict(self.summary),
            "swimmers": [s.as_dict() for s in self.swimmers],
        }


DEFAULT_MILESTONES: Tuple[SeedMilestone, ...] = (
    SeedMilestone(
        "malibu_lease",
        "Execute Malibu LAB lease",
        "2026-06-01",
        (("lease", "malibu"), ("3966", "las flores"), ("310-738-0499",), ("malibu", "lab")),
        "Execute lease 3966 Las Flores Canyon Road Malibu (310-738-0499)",
    ),
    SeedMilestone(
        "houston_meeting",
        "Houston in-person meeting",
        "2026-06-15",
        (("houston", "meeting"), ("carlton", "george", "houston")),
        "Houston in-person meeting (Carlton/George)",
    ),
    SeedMilestone(
        "pepperdine_pipeline",
        "Pepperdine faculty + graduate pipeline",
        "2026-07-15",
        (("pepperdine",), ("faculty", "graduate"), ("scientific", "advisory")),
        "Pepperdine faculty + grad pipeline + scientific advisory",
    ),
    SeedMilestone(
        "podcast_presence",
        "Podcast schedule + internet presence",
        "2026-07-01",
        (("podcast", "schedule"), ("internet", "presence"), ("content", "schedule")),
        "Podcast schedule + internet presence build",
    ),
    SeedMilestone(
        "equipment_cluster",
        "First equipment: DGX, M5 cluster, robotics prototypes",
        "2026-07-31",
        (("dgx",), ("nvidia",), ("m5", "cluster"), ("robotics", "prototype")),
        "First equipment (DGX NVIDIA + M5 cluster + robotics prototypes)",
    ),
    SeedMilestone(
        "nodes_50",
        "50+ SIFTA nodes",
        "2026-11-30",
        (("50", "nodes"), ("50+", "nodes"), ("node", "federation")),
        "Milestones by 2026-11-30: 50+ nodes",
    ),
    SeedMilestone(
        "lois_3",
        "3+ letters of intent",
        "2026-11-30",
        (("3", "loi"), ("3+", "lois"), ("letter", "intent")),
        "Milestones by 2026-11-30: 3+ LOIs",
    ),
    SeedMilestone(
        "patents_3",
        "3+ patent filings",
        "2026-11-30",
        (("3", "patent"), ("3+", "patents"), ("patent", "filing")),
        "Milestones by 2026-11-30: 3+ patents",
    ),
    SeedMilestone(
        "ros_security_beta",
        "Beta ROS + security app",
        "2026-11-30",
        (("ros", "security"), ("beta", "security"), ("robot", "security", "app")),
        "Milestones by 2026-11-30: beta ROS + security app",
    ),
    SeedMilestone(
        "commercial_wordace",
        "Commercial WordACE",
        "2026-11-30",
        (("commercial", "wordace"), ("wordace", "sales"), ("ace", "commercial")),
        "Milestones by 2026-11-30: commercial WordACE",
    ),
)


_EVIDENCE_LEDGER_NAMES = (
    "work_receipts.jsonl",
    "ide_stigmergic_trace.jsonl",
    "outreach_stigmergy_log.jsonl",
    "architect_day_segments.jsonl",
    "alice_first_person_journal.jsonl",
    "app_focus.jsonl",
)


def _parse_due(due_date: Optional[str]) -> Optional[datetime]:
    if not due_date:
        return None
    try:
        return datetime.strptime(due_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _tail_text(path: Path, max_bytes: int = 512 * 1024) -> str:
    if not path.exists():
        return ""
    try:
        with path.open("rb") as fh:
            fh.seek(0, 2)
            end = fh.tell()
            fh.seek(max(0, end - max_bytes))
            return fh.read().decode("utf-8", errors="replace")
    except OSError:
        return ""


def _evidence_rows(root: Path) -> List[Tuple[str, str]]:
    state = root / ".sifta_state"
    rows: List[Tuple[str, str]] = []
    for name in _EVIDENCE_LEDGER_NAMES:
        path = state / name
        raw = _tail_text(path)
        if not raw:
            continue
        for line in raw.splitlines():
            text = line.strip()
            if not text:
                continue
            try:
                obj = json.loads(text)
                blob = json.dumps(obj, ensure_ascii=False, sort_keys=True)
            except Exception:
                blob = text
            rows.append((name, blob.lower()))
    return rows


def _matches(blob: str, groups: Sequence[Sequence[str]]) -> bool:
    for group in groups:
        if all(str(term).lower() in blob for term in group):
            return True
    return False


def _append_jsonl_locked(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(row, ensure_ascii=False) + "\n"
    with path.open("a", encoding="utf-8") as fh:
        try:
            import fcntl

            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            fh.write(line)
            fh.flush()
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        except Exception:
            fh.write(line)
            fh.flush()


def _stamp_physics(row: Dict[str, Any]) -> None:
    try:
        from System.swarm_physics_gate import request_clearance, stamp_receipt

        clearance = request_clearance(cost_class="feather", lane="seed_deal.milestones")
        stamp_receipt(row, clearance)
    except Exception:
        pass


def _score_milestone(
    milestone: SeedMilestone,
    rows: Sequence[Tuple[str, str]],
    *,
    now: datetime,
) -> MilestoneSwimmer:
    refs: List[str] = []
    for ledger_name, blob in rows:
        if _matches(blob, milestone.keyword_groups):
            refs.append(ledger_name)
            if len(refs) >= 6:
                break

    due = _parse_due(milestone.due_date)
    days_left: Optional[float] = None
    if due is not None:
        days_left = (due - now).total_seconds() / 86400.0

    evidence_hits = len(refs)
    evidence_strength = min(1.0, evidence_hits / 2.0)

    if evidence_hits:
        complete_p = 0.35 + 0.6 * evidence_strength
    else:
        complete_p = 0.05

    if days_left is None:
        base_risk = 0.18
    elif days_left < 0:
        base_risk = 0.95
    elif days_left <= 7:
        base_risk = 0.55
    elif days_left <= 21:
        base_risk = 0.35
    elif days_left <= 60:
        base_risk = 0.22
    else:
        base_risk = 0.12

    at_risk_p = base_risk * (1.0 - 0.75 * evidence_strength)
    on_track_p = max(0.0, 1.0 - complete_p - at_risk_p)

    total = complete_p + on_track_p + at_risk_p
    if total <= 0 or not math.isfinite(total):
        complete_p, on_track_p, at_risk_p = 0.05, 0.75, 0.20
    else:
        complete_p /= total
        on_track_p /= total
        at_risk_p /= total

    probs = {"COMPLETE": complete_p, "ON_TRACK": on_track_p, "AT_RISK": at_risk_p}
    status = max(probs, key=probs.get)

    return MilestoneSwimmer(
        swimmer_id=f"seed-{milestone.milestone_id}-{uuid.uuid4().hex[:8]}",
        milestone_id=milestone.milestone_id,
        title=milestone.title,
        due_date=milestone.due_date,
        days_left=days_left,
        evidence_hits=evidence_hits,
        evidence_refs=tuple(sorted(set(refs))),
        complete_p=complete_p,
        on_track_p=on_track_p,
        at_risk_p=at_risk_p,
        status=status,
    )


def evaluate_seed_deal_milestones(
    *,
    root: Path | str = _REPO,
    milestones: Sequence[SeedMilestone] = DEFAULT_MILESTONES,
    now: Optional[datetime] = None,
    write_ledger: bool = True,
) -> SeedDealPosterior:
    """Evaluate the seed-deal milestone posterior.

    ``root`` is the repo root containing ``.sifta_state``. Tests pass a
    temporary root so no local organism state is touched.
    """
    root_p = Path(root)
    now_dt = now or datetime.now(timezone.utc)
    if now_dt.tzinfo is None:
        now_dt = now_dt.replace(tzinfo=timezone.utc)

    rows = _evidence_rows(root_p)
    swimmers = tuple(_score_milestone(m, rows, now=now_dt) for m in milestones)
    summary = {"COMPLETE": 0, "ON_TRACK": 0, "AT_RISK": 0}
    for swimmer in swimmers:
        summary[swimmer.status] = summary.get(swimmer.status, 0) + 1

    posterior = SeedDealPosterior(
        posterior_id=f"seed-posterior-{uuid.uuid4().hex[:12]}",
        ts=time.time(),
        truth_label=_TRUTH_LABEL,
        swimmers=swimmers,
        summary=summary,
    )

    if write_ledger:
        row = posterior.as_dict()
        _stamp_physics(row)
        _append_jsonl_locked(root_p / ".sifta_state" / "seed_deal_milestone_posteriors.jsonl", row)

    return posterior


def format_posterior_for_crucible(posterior: SeedDealPosterior) -> str:
    """Render a compact text block for the Seed Deal Crucible."""
    lines = [
        "MILESTONE SWIMMERS LIVE",
        f"  Posterior {posterior.posterior_id}  |  {posterior.truth_label}",
        (
            "  Summary: "
            f"complete={posterior.summary.get('COMPLETE', 0)}  "
            f"on_track={posterior.summary.get('ON_TRACK', 0)}  "
            f"at_risk={posterior.summary.get('AT_RISK', 0)}"
        ),
    ]
    for s in posterior.swimmers:
        due = s.due_date or "open"
        days = "open" if s.days_left is None else f"{s.days_left:.1f}d"
        refs = ",".join(s.evidence_refs) if s.evidence_refs else "no-ledger-hit-yet"
        lines.append(
            "  "
            f"{s.status:8s}  {s.title}  due={due} ({days})  "
            f"P[c/o/r]={s.complete_p:.2f}/{s.on_track_p:.2f}/{s.at_risk_p:.2f}  "
            f"hits={s.evidence_hits}  refs={refs}"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    post = evaluate_seed_deal_milestones(write_ledger=True)
    print(format_posterior_for_crucible(post))
