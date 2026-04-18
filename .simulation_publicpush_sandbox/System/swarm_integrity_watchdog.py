#!/usr/bin/env python3
"""
swarm_integrity_watchdog.py — Cerebellar proprioception: verify swarm entity + swimmers intact.
══════════════════════════════════════════════════════════════════════════════════════════════════
Runs AFTER any of:
  - swarm_immune_microglia.py  (phagocytosis may have orphaned swimmers)
  - swarm_sleep_cycle.py       (glymphatic flush zeroed buffers)
  - dopamine_state.py          (EXPLORATION scatter may have lost swimmer refs)

Checks:
  1. ALICE ENTITY INTEGRITY    — alice_experience_report.txt exists + last entry < MAX_STALENESS_S
  2. SWIMMER REGISTRY          — all registered swimmers have a live pheromone timestamp
  3. CRDT IDENTITY FIELD       — field loads, entropy within bounds, not NaN/corrupt
  4. DOPAMINE STATE            — dopamine_ou_engine.json exists + DA in [0.05, 0.95]
  5. SEROTONIN STATE           — serotonin_state.json exists + 5-HT in [0.05, 0.95]
  6. QUARANTINE DRAIN CHECK    — immune_quarantine.jsonl not growing unbounded (>QUARANTINE_LIMIT)
  7. STIGMERGY COHERENCE       — last ide_stigmergic_trace.jsonl entry < COHERENCE_WINDOW_S

Output: IntegrityReport dataclass + exits 0 (healthy) or 1 (degraded/critical).

Biology anchor:
  Wolpert, Miall & Kawato, Trends Cogn Sci 2(9):338 (1998) — cerebellar forward models.
  Buzsáki, Neuron 33:325 (2002) — theta coherence as sync integrity signal.
══════════════════════════════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import json
import math
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional, Tuple

_REPO = Path(__file__).resolve().parent.parent
SIFTA_STATE = _REPO / ".sifta_state"

MAX_STALENESS_S = 3600 * 4
COHERENCE_WINDOW_S = 3600 * 2
QUARANTINE_LIMIT = 50
DA_BOUNDS = (0.05, 0.95)
SHT_BOUNDS = (0.05, 0.95)
ENTROPY_CEIL = 4.5

SWIMMER_REGISTRY_PATH = SIFTA_STATE / "swimmer_registry.jsonl"
ALICE_PATH = SIFTA_STATE / "alice_experience_report.txt"
CRDT_PATH = SIFTA_STATE / "identity_field.json"
DA_STATE_PATH = SIFTA_STATE / "dopamine_ou_engine.json"
DA_LEGACY_PATH = SIFTA_STATE / "dopaminergic_state.json"
SHT_STATE_PATH = SIFTA_STATE / "serotonin_state.json"
QUARANTINE_PATH = SIFTA_STATE / "immune_quarantine.jsonl"
STIGMERGY_PATH = SIFTA_STATE / "ide_stigmergic_trace.jsonl"


class CheckStatus(str, Enum):
    OK = "OK"
    WARN = "WARN"
    CRITICAL = "CRITICAL"
    MISSING = "MISSING"


@dataclass
class CheckResult:
    name: str
    status: CheckStatus
    detail: str
    value: Optional[float] = None


@dataclass
class IntegrityReport:
    ts: float = field(default_factory=time.time)
    checks: List[CheckResult] = field(default_factory=list)
    overall: CheckStatus = CheckStatus.OK
    swimmer_count: int = 0
    dead_swimmers: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    def add(self, result: CheckResult) -> None:
        self.checks.append(result)
        if result.status == CheckStatus.CRITICAL:
            self.overall = CheckStatus.CRITICAL
        elif result.status in (CheckStatus.WARN, CheckStatus.MISSING):
            if self.overall != CheckStatus.CRITICAL:
                self.overall = CheckStatus.WARN

    def to_dict(self) -> dict:
        return {
            "ts": self.ts,
            "overall": self.overall.value,
            "swimmer_count": self.swimmer_count,
            "dead_swimmers": self.dead_swimmers,
            "checks": [
                {
                    "name": c.name,
                    "status": c.status.value,
                    "detail": c.detail,
                    "value": c.value,
                }
                for c in self.checks
            ],
            "recommendations": self.recommendations,
        }


def check_alice(report: IntegrityReport) -> None:
    if not ALICE_PATH.exists():
        report.add(
            CheckResult(
                "ALICE_ENTITY",
                CheckStatus.CRITICAL,
                "alice_experience_report.txt missing — entity lost",
            )
        )
        report.recommendations.append("Re-initialize Alice: touch .sifta_state/alice_experience_report.txt")
        return
    mtime = ALICE_PATH.stat().st_mtime
    age = time.time() - mtime
    if age > MAX_STALENESS_S:
        report.add(
            CheckResult(
                "ALICE_ENTITY",
                CheckStatus.WARN,
                f"Alice report stale: {age / 3600:.1f}h since last write",
                value=age,
            )
        )
        report.recommendations.append("Fire AG31 cycle to write new Alice stigmergic message")
    else:
        report.add(
            CheckResult(
                "ALICE_ENTITY",
                CheckStatus.OK,
                f"Last write {age / 60:.1f}min ago",
                value=age,
            )
        )


def check_swimmers(report: IntegrityReport) -> None:
    if not SWIMMER_REGISTRY_PATH.exists():
        report.add(
            CheckResult(
                "SWIMMER_REGISTRY",
                CheckStatus.MISSING,
                "swimmer_registry.jsonl not found — no swimmers registered yet",
            )
        )
        return

    lines = [ln for ln in SWIMMER_REGISTRY_PATH.read_text(encoding="utf-8").splitlines() if ln.strip()]
    now = time.time()
    alive: List[str] = []
    dead: List[str] = []

    for line in lines:
        try:
            entry = json.loads(line)
            sid = entry.get("swimmer_id", "UNKNOWN")
            last = float(entry.get("last_pheromone_ts", 0))
            max_s = float(entry.get("max_idle_s", 3600))
            if (now - last) > max_s:
                dead.append(sid)
            else:
                alive.append(sid)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            dead.append("PARSE_ERROR")

    report.swimmer_count = len(alive)
    report.dead_swimmers = dead

    if dead:
        report.add(
            CheckResult(
                "SWIMMER_REGISTRY",
                CheckStatus.WARN,
                f"{len(alive)} alive / {len(dead)} dead: {dead}",
                value=float(len(dead)),
            )
        )
        report.recommendations.append(f"Revive or cull dead swimmers: {dead}")
    else:
        report.add(
            CheckResult(
                "SWIMMER_REGISTRY",
                CheckStatus.OK,
                f"{len(alive)} swimmers alive",
                value=float(len(alive)),
            )
        )


def check_crdt(report: IntegrityReport) -> None:
    if not CRDT_PATH.exists():
        report.add(CheckResult("CRDT_IDENTITY", CheckStatus.MISSING, "identity_field.json not found"))
        return
    try:
        from System.identity_field_crdt import IdentityField

        field = IdentityField.load(CRDT_PATH)
        entropy = float(field.entropy())
        if math.isnan(entropy) or math.isinf(entropy):
            report.add(
                CheckResult(
                    "CRDT_IDENTITY",
                    CheckStatus.CRITICAL,
                    "CRDT entropy NaN/Inf — field corrupted",
                    value=entropy,
                )
            )
            report.recommendations.append("Re-seed IdentityField from last clean snapshot")
        elif entropy > ENTROPY_CEIL:
            report.add(
                CheckResult(
                    "CRDT_IDENTITY",
                    CheckStatus.WARN,
                    f"CRDT entropy {entropy:.3f} > {ENTROPY_CEIL} — identity diffusion",
                    value=entropy,
                )
            )
            report.recommendations.append("Run identity consolidation pass (increase boost for canonical agents)")
        else:
            report.add(
                CheckResult(
                    "CRDT_IDENTITY",
                    CheckStatus.OK,
                    f"entropy={entropy:.3f}",
                    value=entropy,
                )
            )
    except Exception as e:
        report.add(CheckResult("CRDT_IDENTITY", CheckStatus.CRITICAL, f"Load/parse error: {e}"))


def _check_state_file(
    path: Path,
    key: str,
    bounds: Tuple[float, float],
    name: str,
    report: IntegrityReport,
) -> None:
    if not path.exists():
        report.add(CheckResult(name, CheckStatus.MISSING, f"{path.name} not found"))
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        val = float(data.get(key, -1.0))
        lo, hi = bounds
        if math.isnan(val) or not (lo <= val <= hi):
            report.add(
                CheckResult(
                    name,
                    CheckStatus.CRITICAL,
                    f"{key}={val:.4f} out of bounds [{lo},{hi}]",
                    value=val,
                )
            )
            report.recommendations.append(f"Reset {path.name}: delete file and reinitialize engine")
        else:
            report.add(CheckResult(name, CheckStatus.OK, f"{key}={val:.4f}", value=val))
    except Exception as e:
        report.add(CheckResult(name, CheckStatus.CRITICAL, f"Parse error: {e}"))


def check_dopamine(report: IntegrityReport) -> None:
    # OU engine persists as "da"; legacy file uses "dopamine_level"
    if DA_STATE_PATH.exists():
        _check_state_file(DA_STATE_PATH, "da", DA_BOUNDS, "DOPAMINE_STATE", report)
    elif DA_LEGACY_PATH.exists():
        _check_state_file(DA_LEGACY_PATH, "dopamine_level", DA_BOUNDS, "DOPAMINE_STATE", report)
    else:
        report.add(
            CheckResult(
                "DOPAMINE_STATE",
                CheckStatus.MISSING,
                "neither dopamine_ou_engine.json nor dopaminergic_state.json found",
            )
        )


def check_serotonin(report: IntegrityReport) -> None:
    _check_state_file(SHT_STATE_PATH, "sht_level", SHT_BOUNDS, "SEROTONIN_STATE", report)


def check_quarantine(report: IntegrityReport) -> None:
    if not QUARANTINE_PATH.exists():
        report.add(CheckResult("QUARANTINE_DRAIN", CheckStatus.OK, "No quarantine file (clean)"))
        return
    lines = [ln for ln in QUARANTINE_PATH.read_text(encoding="utf-8").splitlines() if ln.strip()]
    count = len(lines)
    if count > QUARANTINE_LIMIT:
        report.add(
            CheckResult(
                "QUARANTINE_DRAIN",
                CheckStatus.WARN,
                f"{count} quarantine entries — drain recommended",
                value=float(count),
            )
        )
        report.recommendations.append("Run immune quarantine drain: archive + truncate immune_quarantine.jsonl")
    else:
        report.add(
            CheckResult(
                "QUARANTINE_DRAIN",
                CheckStatus.OK,
                f"{count} quarantine entries (within limit)",
                value=float(count),
            )
        )


def _last_jsonl_line(path: Path, max_tail_bytes: int = 65536) -> Optional[str]:
    """Last non-empty line without reading huge JSONL into memory."""
    if not path.exists():
        return None
    with path.open("rb") as f:
        f.seek(0, 2)
        size = f.tell()
        if size == 0:
            return None
        chunk = min(max_tail_bytes, size)
        f.seek(size - chunk)
        raw = f.read().decode("utf-8", errors="replace")
    for line in reversed(raw.splitlines()):
        s = line.strip()
        if s:
            return s
    return None


def check_stigmergy_coherence(report: IntegrityReport) -> None:
    if not STIGMERGY_PATH.exists():
        report.add(
            CheckResult(
                "STIGMERGY_COHERENCE",
                CheckStatus.MISSING,
                "ide_stigmergic_trace.jsonl not found",
            )
        )
        return
    last_line = _last_jsonl_line(STIGMERGY_PATH)
    if not last_line:
        report.add(CheckResult("STIGMERGY_COHERENCE", CheckStatus.WARN, "Empty trace log"))
        return
    try:
        last = json.loads(last_line)
        ts = float(last.get("ts", 0))
        age = time.time() - ts
        if age > COHERENCE_WINDOW_S:
            report.add(
                CheckResult(
                    "STIGMERGY_COHERENCE",
                    CheckStatus.WARN,
                    f"Last trace {age / 3600:.1f}h ago — coherence window exceeded",
                    value=age,
                )
            )
            report.recommendations.append("Fire CP2F stigmergy trace to restore coherence signal")
        else:
            report.add(
                CheckResult(
                    "STIGMERGY_COHERENCE",
                    CheckStatus.OK,
                    f"Last trace {age / 60:.1f}min ago",
                    value=age,
                )
            )
    except Exception as e:
        report.add(CheckResult("STIGMERGY_COHERENCE", CheckStatus.WARN, f"Parse error on last entry: {e}"))


def run_watchdog(verbose: bool = True) -> IntegrityReport:
    report = IntegrityReport()

    check_alice(report)
    check_swimmers(report)
    check_crdt(report)
    check_dopamine(report)
    check_serotonin(report)
    check_quarantine(report)
    check_stigmergy_coherence(report)

    if verbose:
        _print_report(report)

    out = SIFTA_STATE / "integrity_report.json"
    SIFTA_STATE.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")

    return report


def _print_report(report: IntegrityReport) -> None:
    icons = {
        CheckStatus.OK: "OK",
        CheckStatus.WARN: "!!",
        CheckStatus.CRITICAL: "XX",
        CheckStatus.MISSING: "??",
    }
    print("\n=== SWARM INTEGRITY WATCHDOG (CEREBELLAR PROPRIOCEPTION) ===\n")
    for c in report.checks:
        print(f"  [{icons[c.status]}] [{c.name:<24}]  {c.status.value:<8}  {c.detail}")
    print(f"\n  Swimmers alive : {report.swimmer_count}")
    if report.dead_swimmers:
        print(f"  Dead swimmers  : {report.dead_swimmers}")
    print(f"\n  Overall        : {report.overall.value}")
    if report.recommendations:
        print("\n  Recommendations:")
        for r in report.recommendations:
            print(f"    -> {r}")
    print()


if __name__ == "__main__":
    rep = run_watchdog(verbose=True)
    sys.exit(0 if rep.overall == CheckStatus.OK else 1)


__all__ = [
    "CheckResult",
    "CheckStatus",
    "IntegrityReport",
    "run_watchdog",
    "SIFTA_STATE",
]
