"""EPR field memory + ASCII visualization.

A small, read-only organ that maintains a **decay-weighted rolling
buffer of EPR field snapshots** drawn from
`.sifta_state/epr_stigmergic_receipts.jsonl`, and renders them as a
terminal ASCII heatmap so the "memory mechanism" is obvious to watch.

Why this exists
---------------
Item 4 of the Architect directive (2026-05-11): *"Better visualization
of the shared field traces over time so the 'memory' mechanism is
obvious to watch."*

The EPR widget shows the **current** state. This module shows **how
the state has evolved**. A field that genuinely carries memory of
prior measurements should leave a visible time-decay tail; a field
that doesn't, won't.

Public API
----------
- `FieldSnapshot`     — one row from the EPR ledger, normalized.
- `FieldMemory`       — frozen dataclass holding a rolling buffer
                        of snapshots plus decay-weighted aggregates.
- `compute_memory()`  — read the ledger, build the memory.
- `render_ascii(memory, width=60, rows=8)` — terminal heatmap.
- `to_csv(memory)` / `to_json(memory)` — export for matplotlib.

Truth labels (§7.11)
--------------------
- `OBSERVED`        — every snapshot is a real EPR receipt row.
- `OPERATIONAL`     — decay math + buffer aggregation are deterministic
                       and unit-tested.
- `ARCHITECT_DOCTRINE` — the choice of which fields to visualize
                       (`field_energy`, `qm_fidelity`, `stig_qm_residual`)
                       is doctrinal; the renderer adapts to any
                       numeric field that appears in the ledger.

Sandbox-safe: pure stdlib, no matplotlib import at module level
(matplotlib data is just numeric lists; the caller plots them).

Author : Cowork.
"""

from __future__ import annotations

import io
import json
import math
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping, Sequence

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_EPR_RECEIPTS = _STATE / "epr_stigmergic_receipts.jsonl"

TRUTH_LABEL = "EPR_FIELD_MEMORY_V1"

# Default fields to visualize. Caller may override.
DEFAULT_FIELDS: tuple[str, ...] = (
    "field_energy",
    "qm_fidelity",
    "stig_qm_residual",
    "stgm_cost",
    "kappa",
)

# ASCII intensity ramp (low → high). Width-7 to fit narrow terminals.
ASCII_RAMP: str = " .·:+*#@"


@dataclass(frozen=True)
class FieldSnapshot:
    """One row of EPR ledger, normalized for memory storage."""
    ts: float
    values: Mapping[str, float]
    raw_kind: str

    def get(self, key: str, default: float = 0.0) -> float:
        return float(self.values.get(key, default))


@dataclass(frozen=True)
class FieldMemory:
    """Decay-weighted rolling buffer of EPR field snapshots."""
    ts_now: float
    half_life_s: float
    window_s: float
    truth_label: str
    snapshots: tuple[FieldSnapshot, ...]
    fields: tuple[str, ...]
    decayed_means: Mapping[str, float]
    decayed_max: Mapping[str, float]
    n_snapshots: int

    def empty(self) -> bool:
        return self.n_snapshots == 0


def _decay(dt: float, half_life_s: float) -> float:
    if dt <= 0:
        return 1.0
    if half_life_s <= 0:
        return 0.0
    return math.exp(-dt * math.log(2.0) / half_life_s)


def _read_rows(path: Path, *, max_rows: int = 500) -> list[dict]:
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


def compute_memory(
    *,
    now: float | None = None,
    half_life_s: float = 600.0,
    window_s: float = 3600.0,
    fields_of_interest: Sequence[str] | None = None,
    epr_receipts_path: Path | None = None,
) -> FieldMemory:
    """Read recent EPR rows, build the rolling memory.

    Snapshots are kept in chronological order. Each snapshot's
    contribution to `decayed_means` and `decayed_max` is weighted by
    `exp(-dt·ln2 / half_life_s)`.
    """
    now = float(now if now is not None else time.time())
    fields_t = tuple(fields_of_interest or DEFAULT_FIELDS)
    rows = _read_rows(epr_receipts_path or _EPR_RECEIPTS)

    snapshots: list[FieldSnapshot] = []
    for r in rows:
        ts = r.get("ts")
        if not isinstance(ts, (int, float)):
            continue
        dt = now - float(ts)
        if dt < 0 or dt > window_s:
            continue
        vals: dict[str, float] = {}
        for fname in fields_t:
            v = r.get(fname)
            if isinstance(v, (int, float)):
                vals[fname] = float(v)
        if not vals:
            continue
        snapshots.append(
            FieldSnapshot(
                ts=float(ts),
                values=vals,
                raw_kind=str(r.get("kind") or r.get("schema") or ""),
            )
        )

    # Sort by time ascending.
    snapshots.sort(key=lambda s: s.ts)

    weight_sum: dict[str, float] = {f: 0.0 for f in fields_t}
    weighted_sum: dict[str, float] = {f: 0.0 for f in fields_t}
    decayed_max: dict[str, float] = {f: 0.0 for f in fields_t}

    for snap in snapshots:
        d = _decay(now - snap.ts, half_life_s)
        if d == 0:
            continue
        for fname in fields_t:
            v = snap.values.get(fname)
            if v is None:
                continue
            weighted_sum[fname] += d * v
            weight_sum[fname] += d
            decayed_v = d * v
            if decayed_v > decayed_max[fname]:
                decayed_max[fname] = decayed_v

    decayed_means = {
        f: (weighted_sum[f] / weight_sum[f]) if weight_sum[f] > 0 else 0.0
        for f in fields_t
    }

    return FieldMemory(
        ts_now=now,
        half_life_s=half_life_s,
        window_s=window_s,
        truth_label=TRUTH_LABEL,
        snapshots=tuple(snapshots),
        fields=fields_t,
        decayed_means=decayed_means,
        decayed_max=decayed_max,
        n_snapshots=len(snapshots),
    )


# ── ASCII renderer ─────────────────────────────────────────────────────────
def _scale_to_ramp(value: float, vmax: float) -> str:
    if vmax <= 0 or not math.isfinite(value):
        return ASCII_RAMP[0]
    frac = max(0.0, min(1.0, value / vmax))
    idx = int(frac * (len(ASCII_RAMP) - 1))
    return ASCII_RAMP[idx]


def render_ascii(
    memory: FieldMemory,
    *,
    width: int = 60,
    fields: Sequence[str] | None = None,
    show_legend: bool = True,
) -> str:
    """Render the memory as a terminal ASCII heatmap.

    Each row is one field; each column is a time bin from old (left)
    to new (right). Intensity ramp `' .·:+*#@'` indicates value.
    """
    if memory.empty():
        return (
            f"[EPR field memory empty — no events in window "
            f"{memory.window_s:.0f}s; ledger may be quiet]\n"
        )

    field_list = tuple(fields or memory.fields)
    width = max(8, int(width))
    t0 = memory.snapshots[0].ts
    t1 = memory.snapshots[-1].ts
    span = max(t1 - t0, 1e-6)

    bins: dict[str, list[float]] = {f: [0.0] * width for f in field_list}
    bin_counts: list[int] = [0] * width
    for snap in memory.snapshots:
        col = int(((snap.ts - t0) / span) * (width - 1))
        col = max(0, min(width - 1, col))
        bin_counts[col] += 1
        for fname in field_list:
            v = snap.values.get(fname)
            if v is not None:
                bins[fname][col] += v

    # Average within bin where there are entries.
    for fname in field_list:
        for i in range(width):
            if bin_counts[i] > 0:
                bins[fname][i] /= bin_counts[i]

    out = io.StringIO()
    out.write(
        f"EPR field memory @ {memory.ts_now:.0f} "
        f"(window={memory.window_s:.0f}s, half-life={memory.half_life_s:.0f}s, "
        f"snapshots={memory.n_snapshots})\n"
    )
    out.write(f"  time:  [oldest{'─' * (width - 16)}newest]\n")
    for fname in field_list:
        series = bins[fname]
        vmax = max(series) if series else 0.0
        bar = "".join(_scale_to_ramp(v, vmax) for v in series)
        out.write(f"  {fname:18}|{bar}|  max={vmax:.4g}\n")

    if show_legend:
        out.write(
            f"  legend: '{ASCII_RAMP}' low → high; one row per field;\n"
            "  one column = one time-bin from oldest (left) to newest (right).\n"
        )
    return out.getvalue()


# ── Export helpers ─────────────────────────────────────────────────────────
def to_csv(memory: FieldMemory, fields: Sequence[str] | None = None) -> str:
    """Serialize the memory as CSV (header + rows). Caller streams to matplotlib."""
    field_list = tuple(fields or memory.fields)
    out = io.StringIO()
    out.write("ts," + ",".join(field_list) + "\n")
    for snap in memory.snapshots:
        row = [f"{snap.ts:.6f}"]
        for fname in field_list:
            v = snap.values.get(fname)
            row.append("" if v is None else f"{v:.6g}")
        out.write(",".join(row) + "\n")
    return out.getvalue()


def to_json(memory: FieldMemory) -> str:
    """Serialize the memory as JSON."""
    return json.dumps(
        {
            "truth_label": memory.truth_label,
            "ts_now": memory.ts_now,
            "half_life_s": memory.half_life_s,
            "window_s": memory.window_s,
            "fields": list(memory.fields),
            "n_snapshots": memory.n_snapshots,
            "decayed_means": dict(memory.decayed_means),
            "decayed_max": dict(memory.decayed_max),
            "snapshots": [
                {"ts": s.ts, "values": dict(s.values), "kind": s.raw_kind}
                for s in memory.snapshots
            ],
        },
        default=str,
    )


def _cli(argv: Sequence[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(description="EPR field memory ASCII viz.")
    p.add_argument("--window", type=float, default=3600.0)
    p.add_argument("--halflife", type=float, default=600.0)
    p.add_argument("--width", type=int, default=60)
    p.add_argument("--csv", action="store_true",
                   help="Output CSV instead of ASCII heatmap.")
    p.add_argument("--json", action="store_true",
                   help="Output JSON instead of ASCII heatmap.")
    args = p.parse_args(argv)

    mem = compute_memory(
        window_s=args.window, half_life_s=args.halflife,
    )
    if args.csv:
        print(to_csv(mem))
    elif args.json:
        print(to_json(mem))
    else:
        print(render_ascii(mem, width=args.width))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_cli())
