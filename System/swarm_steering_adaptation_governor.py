#!/usr/bin/env python3
"""SIFTA Steering Adaptation Governor — calibrate detector weights from audit.

This module closes the policy_adaptation end of the steering loop:

    route → receipt → self-model → prediction → audit → ADAPTATION

It reads the latest steering_prediction_audit.jsonl row and adjusts a
per-detector weight based on each detector's measured accuracy. The learned
predictor may consume those weights only after paired detector evidence clears
the minimum sample gate. With insufficient data the weight is carried forward
and the self-model falls back to the rule predictor.

§7.12 honesty bound:
    The governor refuses to change any weight until a detector has
    accumulated >=10 paired-prediction samples in the audit. With small
    samples it writes a receipt saying INSUFFICIENT_SAMPLES per detector
    and carries previous weights forward unchanged.

§20.F honesty bound:
    No claim that adapted weights mean Alice is "learning" or "becoming
    self-aware." Weights are HYPOTHESIS-class calibration coefficients
    derived deterministically from ledger receipts. They are consumed only as
    routing calibration coefficients, never as hidden neural weights.

Architect spec (verbatim from 2026-05-14):
    if detector accuracy > 0.75 → weight +0.05
    if detector accuracy < 0.45 → weight -0.05
    if fewer than 10 samples → no change
    clamp weights 0.5–1.5
    append receipt every change

Truth label: STEERING_ADAPTATION_GOVERNOR_V1.
Receipt schema: SIFTA_STEERING_ADAPTATION_GOVERNOR_RECEIPT_V1.
Ledger: .sifta_state/steering_adaptation_governor.jsonl
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
AUDIT_LEDGER = "steering_prediction_audit.jsonl"
ADAPTATION_LEDGER = "steering_adaptation_governor.jsonl"
TRUTH_LABEL = "STEERING_ADAPTATION_GOVERNOR_V1"
TRUTH_BOUNDARY = (
    "Per-detector weights are HYPOTHESIS-class calibration coefficients "
    "derived deterministically from prediction-audit accuracy. They are "
    "NOT neural learned weights and NOT a claim of self-awareness. The "
    "learned predictor may consume them only when paired detector evidence "
    "meets the sample gate; otherwise _predict_next_route() falls back to "
    "the rule predictor."
)

# Architect-specified thresholds (2026-05-14)
MIN_SAMPLES_TO_ADAPT = 10
BOOST_THRESHOLD = 0.75
DAMPEN_THRESHOLD = 0.45
WEIGHT_DELTA = 0.05
WEIGHT_MIN = 0.5
WEIGHT_MAX = 1.5
INIT_WEIGHT = 1.0


def _state_dir(state_dir: str | Path | None = None) -> Path:
    return Path(state_dir) if state_dir is not None else STATE_DIR


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        return []
    return rows


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def latest_audit_row(*, state_dir: str | Path | None = None) -> dict[str, Any] | None:
    """Return the most recent audit row or None when ledger is empty."""
    rows = _read_jsonl(_state_dir(state_dir) / AUDIT_LEDGER)
    return rows[-1] if rows else None


def latest_adaptation_weights(*, state_dir: str | Path | None = None) -> dict[str, float]:
    """Return weights from the most recent adaptation receipt, or {}."""
    rows = _read_jsonl(_state_dir(state_dir) / ADAPTATION_LEDGER)
    if not rows:
        return {}
    last = rows[-1]
    raw = last.get("detector_weights") or {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, float] = {}
    for k, v in raw.items():
        try:
            out[str(k)] = float(v)
        except Exception:
            continue
    return out


# ── Single adaptation step ─────────────────────────────────────────────

@dataclass(frozen=True)
class DetectorAdaptation:
    """The per-detector decision the governor made this cycle."""
    name: str
    sample_count: int
    accuracy: float
    previous_weight: float
    new_weight: float
    delta: float
    status: str           # ADAPTED_BOOST | ADAPTED_DAMPEN | NO_CHANGE | INSUFFICIENT_SAMPLES
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "sample_count": int(self.sample_count),
            "accuracy": round(float(self.accuracy), 4),
            "previous_weight": round(float(self.previous_weight), 4),
            "new_weight": round(float(self.new_weight), 4),
            "delta": round(float(self.delta), 4),
            "status": self.status,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class AdaptationReport:
    detector_weights: dict[str, float]
    adaptations: tuple[DetectorAdaptation, ...]
    audit_trace_id: str | None
    audit_sample_count: int
    overall_status: str          # ADAPTED | NO_CHANGE_INSUFFICIENT_DATA | NO_AUDIT
    reason: str
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    truth_label: str = TRUTH_LABEL

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "truth_label": self.truth_label,
            "detector_weights": {
                k: round(float(v), 4)
                for k, v in sorted(self.detector_weights.items())
            },
            "adaptations": [a.to_dict() for a in self.adaptations],
            "audit_trace_id": self.audit_trace_id,
            "audit_sample_count": int(self.audit_sample_count),
            "overall_status": self.overall_status,
            "reason": self.reason,
        }


def _adapt_one(
    name: str,
    sample_count: int,
    accuracy: float,
    previous_weight: float,
) -> DetectorAdaptation:
    """Apply the Architect-specified rule to a single detector."""
    if sample_count < MIN_SAMPLES_TO_ADAPT:
        return DetectorAdaptation(
            name=name,
            sample_count=sample_count,
            accuracy=accuracy,
            previous_weight=previous_weight,
            new_weight=previous_weight,
            delta=0.0,
            status="INSUFFICIENT_SAMPLES",
            reason=f"{sample_count} < {MIN_SAMPLES_TO_ADAPT} samples; weight held.",
        )
    if accuracy > BOOST_THRESHOLD:
        target = _clamp(previous_weight + WEIGHT_DELTA, WEIGHT_MIN, WEIGHT_MAX)
        delta = target - previous_weight
        return DetectorAdaptation(
            name=name,
            sample_count=sample_count,
            accuracy=accuracy,
            previous_weight=previous_weight,
            new_weight=target,
            delta=delta,
            status="ADAPTED_BOOST" if delta > 0 else "NO_CHANGE",
            reason=(
                f"accuracy={accuracy:.3f} > {BOOST_THRESHOLD}; "
                f"boosted by {delta:+.3f}"
                if delta > 0
                else f"accuracy={accuracy:.3f} but weight already at clamp."
            ),
        )
    if accuracy < DAMPEN_THRESHOLD:
        target = _clamp(previous_weight - WEIGHT_DELTA, WEIGHT_MIN, WEIGHT_MAX)
        delta = target - previous_weight
        return DetectorAdaptation(
            name=name,
            sample_count=sample_count,
            accuracy=accuracy,
            previous_weight=previous_weight,
            new_weight=target,
            delta=delta,
            status="ADAPTED_DAMPEN" if delta < 0 else "NO_CHANGE",
            reason=(
                f"accuracy={accuracy:.3f} < {DAMPEN_THRESHOLD}; "
                f"dampened by {delta:+.3f}"
                if delta < 0
                else f"accuracy={accuracy:.3f} but weight already at clamp."
            ),
        )
    return DetectorAdaptation(
        name=name,
        sample_count=sample_count,
        accuracy=accuracy,
        previous_weight=previous_weight,
        new_weight=previous_weight,
        delta=0.0,
        status="NO_CHANGE",
        reason=(
            f"accuracy={accuracy:.3f} in mid-band "
            f"[{DAMPEN_THRESHOLD}, {BOOST_THRESHOLD}]; weight held."
        ),
    )


# ── Main adaptation step ───────────────────────────────────────────────

def adapt(
    *,
    audit_row: dict[str, Any] | None = None,
    previous_weights: dict[str, float] | None = None,
    state_dir: str | Path | None = None,
) -> AdaptationReport:
    """Run one adaptation cycle.

    If ``audit_row`` is None, the latest audit row is read from the audit
    ledger. If ``previous_weights`` is None, the latest adaptation receipt
    is consulted; if there are none, every detector starts at INIT_WEIGHT
    (1.0).
    """
    if audit_row is None:
        audit_row = latest_audit_row(state_dir=state_dir)
    if previous_weights is None:
        previous_weights = latest_adaptation_weights(state_dir=state_dir)

    if not audit_row:
        # No audit available — return a no-op report at default weights.
        return AdaptationReport(
            detector_weights=dict(previous_weights),
            adaptations=tuple(),
            audit_trace_id=None,
            audit_sample_count=0,
            overall_status="NO_AUDIT",
            reason="No audit row available; weights carried forward unchanged.",
        )

    by_detector = audit_row.get("by_dominant_detector") or {}
    if not isinstance(by_detector, dict):
        by_detector = {}

    adaptations: list[DetectorAdaptation] = []
    new_weights = dict(previous_weights)
    any_adapted = False
    for name, stats in sorted(by_detector.items()):
        try:
            sample_count = int(stats.get("sample_count", 0))
            accuracy = float(stats.get("accuracy", 0.0))
        except Exception:
            continue
        prev = float(new_weights.get(name, INIT_WEIGHT))
        decision = _adapt_one(name, sample_count, accuracy, prev)
        adaptations.append(decision)
        new_weights[name] = decision.new_weight
        if decision.status in ("ADAPTED_BOOST", "ADAPTED_DAMPEN"):
            any_adapted = True

    audit_total = int(audit_row.get("sample_count") or 0)
    audit_trace = str(audit_row.get("trace_id") or "") or None

    if any_adapted:
        overall = "ADAPTED"
        reason = "; ".join(
            f"{a.name}: {a.status} ({a.reason})"
            for a in adaptations
            if a.status in ("ADAPTED_BOOST", "ADAPTED_DAMPEN")
        )
    else:
        overall = "NO_CHANGE_INSUFFICIENT_DATA"
        details = [
            f"{a.name}: {a.status} (n={a.sample_count}, acc={a.accuracy:.3f})"
            for a in adaptations
        ] or ["no detectors in audit row"]
        reason = "; ".join(details)

    return AdaptationReport(
        detector_weights=new_weights,
        adaptations=tuple(adaptations),
        audit_trace_id=audit_trace,
        audit_sample_count=audit_total,
        overall_status=overall,
        reason=reason,
    )


# ── Receipts ───────────────────────────────────────────────────────────

def write_adaptation_receipt(
    report: AdaptationReport,
    *,
    state_dir: str | Path | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """Append a sha256-signed adaptation receipt to the ledger."""
    ts = float(now if now is not None else time.time())
    payload = report.to_dict()
    sign_body = {k: v for k, v in payload.items() if k != "trace_id"}
    sha = hashlib.sha256(
        json.dumps(sign_body, sort_keys=True, separators=(",", ":"),
                   default=str).encode("utf-8")
    ).hexdigest()
    row = dict(payload)
    row.update({
        "schema": "SIFTA_STEERING_ADAPTATION_GOVERNOR_RECEIPT_V1",
        "ts": ts,
        "sha256": sha,
        "truth_boundary": TRUTH_BOUNDARY,
    })
    path = _state_dir(state_dir) / ADAPTATION_LEDGER
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return row


def adaptation_prompt_block(report: AdaptationReport | None = None) -> str:
    """Compact block exposing the current detector weights to a caller."""
    if report is None:
        rep = adapt()
    else:
        rep = report
    lines = [
        "STEERING ADAPTATION GOVERNOR (HYPOTHESIS — sample-gated calibration)",
        f"  status: {rep.overall_status}",
        f"  audit_sample_count: {rep.audit_sample_count}",
    ]
    if rep.detector_weights:
        lines.append("  detector_weights:")
        for name, w in sorted(rep.detector_weights.items()):
            lines.append(f"    - {name}: {w:.3f}")
    if rep.adaptations:
        non_default = [
            a for a in rep.adaptations
            if a.status in ("ADAPTED_BOOST", "ADAPTED_DAMPEN")
        ]
        if non_default:
            lines.append("  changes:")
            for a in non_default:
                lines.append(f"    - {a.name}: {a.delta:+.3f} ({a.status})")
    lines.append(f"  truth: {TRUTH_LABEL}")
    return "\n".join(lines)


def run_governor(
    *,
    state_dir: str | Path | None = None,
    write: bool = True,
) -> tuple[AdaptationReport, dict[str, Any] | None]:
    """Convenience: read latest audit + prev weights, adapt, optionally write."""
    report = adapt(state_dir=state_dir)
    receipt = (
        write_adaptation_receipt(report, state_dir=state_dir)
        if write else None
    )
    return report, receipt


__all__ = [
    "ADAPTATION_LEDGER",
    "AUDIT_LEDGER",
    "BOOST_THRESHOLD",
    "DAMPEN_THRESHOLD",
    "INIT_WEIGHT",
    "MIN_SAMPLES_TO_ADAPT",
    "TRUTH_BOUNDARY",
    "TRUTH_LABEL",
    "WEIGHT_DELTA",
    "WEIGHT_MAX",
    "WEIGHT_MIN",
    "AdaptationReport",
    "DetectorAdaptation",
    "adapt",
    "adaptation_prompt_block",
    "latest_adaptation_weights",
    "latest_audit_row",
    "run_governor",
    "write_adaptation_receipt",
]


if __name__ == "__main__":
    report, receipt = run_governor(write=False)
    print(adaptation_prompt_block(report))
    print()
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
