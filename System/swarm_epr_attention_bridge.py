"""EPR ↔ Architect Attention Field bridge.

A small, read-only sense-fusion organ. It wires Cursor's
`Applications/sifta_epr_stigmergic_widget.py` to the Architect Attention
Field (`swarm_architect_attention_field`) so that:

1. When the EPR widget runs a batch, the resulting `field_energy` and
   `stig_qm_residual` are projected onto the **attention vector** as
   synthetic trace rows tagged `epr_stigmergic`. The widget's running
   reality becomes part of George's measured attention shape.

2. The reverse query is exposed: `attention_for_epr_topics(field)`
   returns a 0..1 score telling the widget — or anyone — how aligned
   George's current attention is with EPR / Bell / quantum / field
   vocabulary. The widget can use this to dim its visualization when
   George is looking elsewhere, or boost its salience when he is
   focused on it.

Lane (§4.4)
-----------
This module does NOT mutate the EPR widget. It only **reads** Cursor's
ledger at `.sifta_state/epr_stigmergic_receipts.jsonl` and feeds the
attention field. Cursor still owns the widget.

Truth labels (§7.11)
--------------------
- `OBSERVED`        — every input is a real ledger row written by the
                       EPR widget.
- `OPERATIONAL`     — projection math is deterministic, unit-tested.
- `ARCHITECT_DOCTRINE` — the choice to map `field_energy` and
                       `stig_qm_residual` onto specific attention axes
                       is a doctrinal mapping; future Architects may
                       refine the weights.
- `FORBIDDEN`        — never invents an EPR row; never writes one to
                       Cursor's ledger.

Author : Cowork (Claude Opus 4.7).
"""

from __future__ import annotations

import json
import math
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from System.swarm_architect_attention_field import (
    AXIS_NAMES,
    AttentionField,
    compute_attention,
    salience_for,
)

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_EPR_RECEIPTS = _STATE / "epr_stigmergic_receipts.jsonl"
_BRIDGE_LEDGER = _STATE / "epr_attention_bridge.jsonl"

TRUTH_LABEL = "EPR_ATTENTION_BRIDGE_V1"

# How much each numeric EPR field maps onto the attention axes (un-decayed).
# Keys are EPR receipt field names; values are dicts mapping axis-name → weight.
# These weights are ARCHITECT_DOCTRINE.
_EPR_FIELD_AXIS_WEIGHTS: Mapping[str, Mapping[str, float]] = {
    # field_energy is straight field_dynamics evidence.
    "field_energy":      {"field_dynamics": 1.0, "alice_health": 0.2},
    # The closer stigmergic correlations are to QM (low residual), the
    # stronger the "Alice is approaching QM-like behavior" signal.
    "stig_qm_residual":  {"field_dynamics": 0.4, "drift": 0.6},
    # qm_fidelity directly tracks how QM-like the run was.
    "qm_fidelity":       {"field_dynamics": 0.8},
    # STGM cost is an infra signal (compute + economy).
    "stgm_cost":         {"infra": 0.8, "field_dynamics": 0.2},
    # Number of pairs is code/run intensity.
    "total_pairs":       {"code": 0.6, "field_dynamics": 0.3},
}

# Topic keywords for the reverse query.
EPR_TOPIC_KEYWORDS: tuple[str, ...] = (
    "epr", "bell", "chsh", "tsirelson", "entanglement", "singlet",
    "swimmer", "stigmergy", "field", "correlation", "nonlocality",
    "quantum", "contextual", "loophole",
)


@dataclass(frozen=True)
class EPRAttentionBridge:
    """One snapshot of the EPR ↔ Attention bridge."""
    ts: float
    truth_label: str
    n_epr_rows_absorbed: int
    epr_share_of_attention: float   # what fraction of attention is EPR-shaped
    epr_topic_salience: float       # salience_for(EPR_TOPIC_KEYWORDS)
    axis_contribution: Mapping[str, float]   # per-axis weight added from EPR
    field_energy_recent: float      # decay-weighted recent field_energy
    qm_fidelity_recent: float       # decay-weighted recent qm_fidelity
    homeworld_serial: str

    def to_jsonable(self) -> dict:
        return {
            "ts": self.ts,
            "truth_label": self.truth_label,
            "n_epr_rows_absorbed": self.n_epr_rows_absorbed,
            "epr_share_of_attention": self.epr_share_of_attention,
            "epr_topic_salience": self.epr_topic_salience,
            "axis_contribution": dict(self.axis_contribution),
            "field_energy_recent": self.field_energy_recent,
            "qm_fidelity_recent": self.qm_fidelity_recent,
            "homeworld_serial": self.homeworld_serial,
        }


def _decay(dt: float, half_life_s: float) -> float:
    if dt <= 0:
        return 1.0
    if half_life_s <= 0:
        return 0.0
    return math.exp(-dt * math.log(2.0) / half_life_s)


def _read_epr_rows(path: Path, *, max_rows: int = 200) -> list[dict]:
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


def attention_for_epr_topics(
    field_obj: AttentionField | None = None,
) -> float:
    """How aligned is current attention with EPR / Bell / field vocabulary?

    Returns 0..1. 0 means George's attention shows zero EPR-shaped signal;
    1 would be a pure EPR projection.
    """
    return salience_for(EPR_TOPIC_KEYWORDS, field_obj=field_obj)


def compute_bridge(
    *,
    now: float | None = None,
    half_life_s: float = 600.0,
    window_s: float = 3600.0,
    epr_receipts_path: Path | None = None,
    homeworld_serial: str | None = None,
    attention_field: AttentionField | None = None,
) -> EPRAttentionBridge:
    """Read recent EPR rows, project, fuse with current attention.

    Decay half-life defaults to 10 minutes — short enough that the bridge
    "forgets" old EPR activity quickly, long enough that a multi-batch
    run still registers.
    """
    now = float(now if now is not None else time.time())
    rows = _read_epr_rows(epr_receipts_path or _EPR_RECEIPTS)

    contrib: dict[str, float] = {name: 0.0 for name in AXIS_NAMES}
    field_energy_sum = 0.0
    fidelity_sum = 0.0
    weight_sum = 0.0
    n_absorbed = 0

    for r in rows:
        ts = r.get("ts")
        if not isinstance(ts, (int, float)):
            continue
        dt = now - float(ts)
        if dt < 0 or dt > window_s:
            continue
        d = _decay(dt, half_life_s)
        if d == 0:
            continue
        absorbed = False
        for key, axis_map in _EPR_FIELD_AXIS_WEIGHTS.items():
            val = r.get(key)
            if isinstance(val, (int, float)):
                # Normalize gently — log1p on positive values keeps a
                # huge field_energy from drowning every other axis.
                if val > 0:
                    norm = math.log1p(val)
                elif val < 0:
                    norm = math.log1p(-val) * 0.5
                else:
                    norm = 0.0
                for axis_name, weight in axis_map.items():
                    contrib[axis_name] += d * norm * weight
                absorbed = True
        fe = r.get("field_energy")
        if isinstance(fe, (int, float)):
            field_energy_sum += d * float(fe)
            weight_sum += d
        fid = r.get("qm_fidelity")
        if isinstance(fid, (int, float)):
            fidelity_sum += d * float(fid)
        if absorbed:
            n_absorbed += 1

    field_energy_recent = field_energy_sum / weight_sum if weight_sum > 0 else 0.0
    qm_fidelity_recent = fidelity_sum / weight_sum if weight_sum > 0 else 0.0

    if attention_field is None:
        attention_field = compute_attention(now=now)
    epr_share = attention_field.as_axis_map().get("field_dynamics", 0.0)
    epr_topic = attention_for_epr_topics(field_obj=attention_field)

    serial = homeworld_serial or attention_field.homeworld_serial

    return EPRAttentionBridge(
        ts=now,
        truth_label=TRUTH_LABEL,
        n_epr_rows_absorbed=n_absorbed,
        epr_share_of_attention=float(epr_share),
        epr_topic_salience=float(epr_topic),
        axis_contribution=contrib,
        field_energy_recent=field_energy_recent,
        qm_fidelity_recent=qm_fidelity_recent,
        homeworld_serial=str(serial),
    )


def deposit(bridge: EPRAttentionBridge, path: Path | None = None) -> Path:
    """Append one snapshot to `.sifta_state/epr_attention_bridge.jsonl`."""
    out = path or _BRIDGE_LEDGER
    out.parent.mkdir(parents=True, exist_ok=True)
    row = {"schema": TRUTH_LABEL, **bridge.to_jsonable()}
    with out.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, default=str) + "\n")
    return out


def _cli(argv: Sequence[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(description="EPR ↔ Attention bridge.")
    p.add_argument("--deposit", action="store_true",
                   help="Append the snapshot row to the bridge ledger.")
    args = p.parse_args(argv)
    b = compute_bridge()
    print(json.dumps(b.to_jsonable(), indent=2, default=str))
    if args.deposit:
        out = deposit(b)
        print(f"\nappended → {out}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_cli())
