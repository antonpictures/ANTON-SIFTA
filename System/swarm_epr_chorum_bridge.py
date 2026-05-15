"""EPR ↔ Chorum Gate pressure bridge (advisory-only).

When the EPR widget runs hot — many batches, high field energy, low
QM-residual — the swarm is sustaining tight stigmergic correlation
across multiple swimmers in a short window. Per covenant §6 (Social
Frame Rule), strong correlation activity is a moment when Alice should
be **more careful** about which actions she claims, not less.

This module is the read-only advisory bridge. It:

1. Reads recent rows from `.sifta_state/epr_stigmergic_receipts.jsonl`.
2. Computes a `correlation_activity_rate`: events per minute × the
   inverse of `stig_qm_residual` (lower residual ⇒ tighter correlation
   ⇒ higher pressure).
3. Suggests an `enforcement_mode_advisory` — `passive` / `advisory` /
   `strict` — based on threshold bands.
4. Appends an `EPR_PRESSURE_ADVISORY` row to the chorum gate's existing
   log file (`chorum_gate_log.jsonl`). The Chorum Gate operator polls
   that log for advisory inputs.

Hard rule (§4.4 #2 and §8.3 #6)
-------------------------------
This bridge NEVER mutates `chorum_gate_state.json`. Enforcement mode
changes require explicit Architect GO. The bridge writes an advisory
row only. The Chorum Gate may consume it, ignore it, or escalate it —
that is the gate's decision, not the bridge's.

Truth labels (§7.11)
--------------------
- `OBSERVED`        — real EPR receipt rows.
- `OPERATIONAL`     — rate math is deterministic, unit-tested.
- `ARCHITECT_DOCTRINE` — the thresholds (0.5 / 2.0 events·min⁻¹·resid⁻¹)
                       are Architect-tunable doctrine.
- `FORBIDDEN`        — never mutates chorum state; never invents EPR rows.

Author : Cowork (Claude Opus 4.7).
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_EPR_RECEIPTS = _STATE / "epr_stigmergic_receipts.jsonl"
_CHORUM_LOG = _STATE / "chorum_gate_log.jsonl"

TRUTH_LABEL = "EPR_CHORUM_PRESSURE_BRIDGE_V1"

# Enforcement-band thresholds (events·min⁻¹ × inverse-residual weight).
# ARCHITECT_DOCTRINE: tune by env var, never hard-mutate.
LOW_PRESSURE_THRESHOLD: float = float(
    os.environ.get("SIFTA_EPR_CHORUM_LOW_PRESSURE", "0.5")
)
HIGH_PRESSURE_THRESHOLD: float = float(
    os.environ.get("SIFTA_EPR_CHORUM_HIGH_PRESSURE", "2.0")
)

# Constants for the gate's enforcement vocabulary (mirrored from
# `swarm_chorum_gate`). Not imported to keep this module loadable in
# sandbox tests with no Qt / no chorum dependency.
ENFORCEMENT_PASSIVE = "passive"
ENFORCEMENT_ADVISORY = "advisory"
ENFORCEMENT_STRICT = "strict"


@dataclass(frozen=True)
class EPRChorumAdvisory:
    """One advisory snapshot."""

    ts: float
    truth_label: str
    window_s: float
    n_events_in_window: int
    rate_events_per_min: float
    mean_inverse_residual: float
    pressure: float
    enforcement_mode_advisory: str
    rationale: str
    homeworld_serial: str

    def to_jsonable(self) -> dict:
        return asdict(self)


def _read_epr_rows(path: Path, *, max_rows: int = 500) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(r, dict):
                    rows.append(r)
    except Exception:
        return []
    if max_rows and len(rows) > max_rows:
        rows = rows[-max_rows:]
    return rows


def _classify_pressure(pressure: float) -> tuple[str, str]:
    """Pick an enforcement-mode advisory + a one-line rationale."""
    if pressure >= HIGH_PRESSURE_THRESHOLD:
        return (
            ENFORCEMENT_STRICT,
            f"pressure {pressure:.2f} ≥ HIGH {HIGH_PRESSURE_THRESHOLD:.2f} — "
            "tight stigmergic correlations across many swimmers; recommend "
            "strict quorum on high+critical actions.",
        )
    if pressure >= LOW_PRESSURE_THRESHOLD:
        return (
            ENFORCEMENT_ADVISORY,
            f"pressure {pressure:.2f} ≥ LOW {LOW_PRESSURE_THRESHOLD:.2f} — "
            "elevated correlation activity; recommend advisory warnings "
            "on medium+ actions.",
        )
    return (
        ENFORCEMENT_PASSIVE,
        f"pressure {pressure:.2f} < LOW {LOW_PRESSURE_THRESHOLD:.2f} — "
        "background EPR activity; passive logging is sufficient.",
    )


def compute_advisory(
    *,
    now: float | None = None,
    window_s: float = 300.0,
    epr_receipts_path: Path | None = None,
    homeworld_serial: str | None = None,
) -> EPRChorumAdvisory:
    """Read recent EPR events, compute pressure + enforcement advisory."""
    now = float(now if now is not None else time.time())
    rows = _read_epr_rows(epr_receipts_path or _EPR_RECEIPTS)

    n = 0
    residual_sum = 0.0
    residual_count = 0
    for r in rows:
        ts = r.get("ts")
        if not isinstance(ts, (int, float)):
            continue
        if (now - float(ts)) > window_s or (now - float(ts)) < 0:
            continue
        n += 1
        res = r.get("stig_qm_residual")
        if isinstance(res, (int, float)) and float(res) > 0:
            residual_sum += float(res)
            residual_count += 1

    rate_per_min = n / max(window_s / 60.0, 1e-9)
    mean_residual = (residual_sum / residual_count) if residual_count > 0 else 0.0
    inv_residual = (1.0 / mean_residual) if mean_residual > 0 else 0.0
    pressure = rate_per_min * inv_residual

    advisory, rationale = _classify_pressure(pressure)
    serial = homeworld_serial or os.environ.get(
        "SIFTA_HOMEWORLD_SERIAL", "UNKNOWN"
    )

    return EPRChorumAdvisory(
        ts=now,
        truth_label=TRUTH_LABEL,
        window_s=window_s,
        n_events_in_window=n,
        rate_events_per_min=rate_per_min,
        mean_inverse_residual=inv_residual,
        pressure=pressure,
        enforcement_mode_advisory=advisory,
        rationale=rationale,
        homeworld_serial=str(serial),
    )


def deposit_advisory(
    advisory: EPRChorumAdvisory,
    *,
    chorum_log_path: Path | None = None,
) -> Path:
    """Append the advisory to chorum_gate_log.jsonl.

    Writes a row tagged `kind: EPR_PRESSURE_ADVISORY` so the Chorum Gate
    operator can filter it out from gate verdicts. The gate decides
    whether to act on the advisory; this function never mutates state.
    """
    out = chorum_log_path or _CHORUM_LOG
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = advisory.to_jsonable()
    sig = hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()
    row = {
        "ts": advisory.ts,
        "event": "EPR_PRESSURE_ADVISORY",
        "kind": "EPR_PRESSURE_ADVISORY",
        "trace_id": str(uuid.uuid4()),
        "schema": TRUTH_LABEL,
        "advisory_only": True,
        "mutates_chorum_state": False,
        **payload,
        "sha256": sig,
    }
    with out.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, default=str) + "\n")
    return out


def _cli(argv: Sequence[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(description="EPR ↔ Chorum pressure bridge.")
    p.add_argument("--deposit", action="store_true",
                   help="Append the advisory to chorum_gate_log.jsonl.")
    p.add_argument("--window", type=float, default=300.0)
    args = p.parse_args(argv)
    a = compute_advisory(window_s=args.window)
    print(json.dumps(a.to_jsonable(), indent=2, default=str))
    if args.deposit:
        out = deposit_advisory(a)
        print(f"\nappended → {out}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_cli())
