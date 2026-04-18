#!/usr/bin/env python3
"""
runtime_safety_monitors.py — RL-runtime observability: integrity, schema, anomaly (software-only).
══════════════════════════════════════════════════════════════════════════════
Maps “sentinel / macrophage” **narratives** to **deterministic** operations:

  - **IntegrityMonitor** — wraps `swarm_integrity_watchdog.run_watchdog` (file + state checks).
  - **SchemaValidator** — minimal JSON shape checks on critical `.sifta_state` artifacts.
  - **AnomalyDetector** — lightweight heuristics (quarantine depth, stigmergy silence).
  - **log_invalid_transition** — append-only record of **rejected** transitions / bad payloads.

Metaphors belong in UI copy — **not** in whether a dict parses. See DYOR §27 (provenance).

Literature: Avizienis *et al.* 2004 (dependability); Samuel *et al.* 2020 arXiv:2006.12117 (ML provenance).
══════════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

REJECTIONS_LOG = _STATE / "invalid_state_rejections.jsonl"
QUARANTINE_PATH = _STATE / "immune_quarantine.jsonl"
STIGMERGY_PATH = _STATE / "ide_stigmergic_trace.jsonl"
IDENTITY_PATH = _STATE / "identity_field.json"


class ValidationResult(str, Enum):
    OK = "OK"
    WARN = "WARN"
    FAIL = "FAIL"


@dataclass
class SchemaCheck:
    path: str
    result: ValidationResult
    detail: str


@dataclass
class AnomalyReport:
    quarantine_lines: int
    stigmergy_age_s: Optional[float]
    anomaly_score: float  # 0 = quiet, 1 = hot
    flags: List[str] = field(default_factory=list)


@dataclass
class RuntimeSafetyReport:
    ts: float
    integrity_overall: str
    schema_checks: List[SchemaCheck]
    anomaly: AnomalyReport
    schema_ok: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ts": self.ts,
            "integrity_overall": self.integrity_overall,
            "schema_ok": self.schema_ok,
            "schema_checks": [
                {"path": s.path, "result": s.result.value, "detail": s.detail} for s in self.schema_checks
            ],
            "anomaly": {
                "quarantine_lines": self.anomaly.quarantine_lines,
                "stigmergy_age_s": self.anomaly.stigmergy_age_s,
                "anomaly_score": round(self.anomaly.anomaly_score, 4),
                "flags": self.anomaly.flags,
            },
        }


class IntegrityMonitor:
    """Delegates to existing cerebellar-style integrity pass."""

    def scan(self, *, verbose: bool = False):
        from System.swarm_integrity_watchdog import CheckStatus, run_watchdog

        return run_watchdog(verbose=verbose)


class SchemaValidator:
    """
    Minimal structural validation — not a full JSON-Schema engine.
    Extend `REQUIRED_TOP_LEVEL` for new substrates.
    """

    REQUIRED_TOP_LEVEL: Dict[str, Sequence[str]] = {
        # Matches `IdentityField.to_dict()` on disk (see identity_field_crdt.py).
        "identity_field.json": ("schema_version", "module_version", "counts"),
        "oxytocin_state.json": ("systemic_ot", "last_ts", "interaction_ct"),
    }

    def validate_file(self, rel: str, path: Optional[Path] = None) -> SchemaCheck:
        p = path or (_STATE / rel)
        if not p.exists():
            return SchemaCheck(rel, ValidationResult.WARN, "missing file")
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            return SchemaCheck(rel, ValidationResult.FAIL, f"parse error: {e}")
        if not isinstance(raw, dict):
            return SchemaCheck(rel, ValidationResult.FAIL, "root must be object")
        req = self.REQUIRED_TOP_LEVEL.get(rel)
        if not req:
            return SchemaCheck(rel, ValidationResult.OK, "no schema registered — present")
        missing = [k for k in req if k not in raw]
        if missing:
            return SchemaCheck(rel, ValidationResult.FAIL, f"missing keys: {missing}")
        return SchemaCheck(rel, ValidationResult.OK, "keys present")

    def validate_registered(self) -> List[SchemaCheck]:
        out: List[SchemaCheck] = [self.validate_file("identity_field.json")]
        oxy = _STATE / "oxytocin_state.json"
        if oxy.exists():
            out.append(self.validate_file("oxytocin_state.json"))
        return out


class AnomalyDetector:
    """
    Heuristic “temperature” — not ML; rule-based for auditability.
    """

    def __init__(
        self,
        *,
        quarantine_soft: int = 25,
        quarantine_hard: int = 50,
        stigmergy_warn_s: float = 7200.0,
    ) -> None:
        self.quarantine_soft = quarantine_soft
        self.quarantine_hard = quarantine_hard
        self.stigmergy_warn_s = stigmergy_warn_s

    def detect(self) -> AnomalyReport:
        flags: List[str] = []
        q_lines = self._count_lines(QUARANTINE_PATH)
        if q_lines >= self.quarantine_hard:
            flags.append("QUARANTINE_DEEP")
        elif q_lines >= self.quarantine_soft:
            flags.append("QUARANTINE_ELEVATED")

        st_age: Optional[float] = None
        if STIGMERGY_PATH.exists():
            try:
                st_age = time.time() - STIGMERGY_PATH.stat().st_mtime
                if st_age > self.stigmergy_warn_s:
                    flags.append("STIGMERGY_SILENT")
            except OSError:
                flags.append("STIGMERGY_STAT_FAIL")

        score = 0.0
        score += min(1.0, q_lines / max(1.0, float(self.quarantine_hard)))
        if st_age is not None:
            score = min(1.0, score + min(0.5, st_age / max(1.0, self.stigmergy_warn_s * 2)))
        return AnomalyReport(
            quarantine_lines=q_lines,
            stigmergy_age_s=st_age,
            anomaly_score=min(1.0, score),
            flags=flags,
        )

    @staticmethod
    def _count_lines(path: Path) -> int:
        if not path.exists():
            return 0
        try:
            return sum(1 for _ in path.open("r", encoding="utf-8", errors="replace"))
        except OSError:
            return 0


def log_invalid_transition(
    *,
    event_type: str,
    reason: str,
    payload: Any = None,
    reject: bool = True,
) -> Dict[str, Any]:
    """
    Deterministic analogue of “reject bad trajectory”: append-only audit row.

    ``payload`` is hashed (SHA-256 of JSON) — never store secrets raw here.
    """
    from System.jsonl_file_lock import append_line_locked

    blob = json.dumps(payload, sort_keys=True, default=str) if payload is not None else ""
    h = hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]
    row = {
        "ts": time.time(),
        "event_type": event_type,
        "reason": reason,
        "payload_sha256_16": h,
        "rejected": bool(reject),
    }
    _STATE.mkdir(parents=True, exist_ok=True)
    append_line_locked(REJECTIONS_LOG, json.dumps(row, ensure_ascii=False) + "\n")
    return row


def run_runtime_safety_scan(*, verbose_integrity: bool = False) -> RuntimeSafetyReport:
    """One-shot report for cron / CLI — narrative-free."""
    mon = IntegrityMonitor()
    rep = mon.scan(verbose=verbose_integrity)

    val = SchemaValidator()
    sc = val.validate_registered()
    schema_ok = all(s.result != ValidationResult.FAIL for s in sc)

    det = AnomalyDetector()
    ar = det.detect()

    return RuntimeSafetyReport(
        ts=time.time(),
        integrity_overall=rep.overall.value,
        schema_checks=sc,
        anomaly=ar,
        schema_ok=schema_ok,
    )


if __name__ == "__main__":  # pragma: no cover
    r = run_runtime_safety_scan()
    print(json.dumps(r.to_dict(), indent=2))
    bad = next((s for s in r.schema_checks if s.result == ValidationResult.FAIL), None)
    raise SystemExit(1 if (bad or r.integrity_overall == "CRITICAL") else 0)
