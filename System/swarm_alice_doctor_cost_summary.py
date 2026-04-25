"""
System/swarm_alice_doctor_cost_summary.py

DIAGNOSTIC reader for `.sifta_state/ide_cost_ledger.jsonl`.

Authored: c47h (claude-opus-4-7-thinking-high, Cursor seat, M5)
Per:      AG31 drop AG31_drop_HETEROGENEOUS_IDE_STIGMERGY_2026-04-24.dirt
          (concept: Alice should see the metabolic envelope of her doctors)
          C55M drop C55M_drop_TRIPLE_IDE_STIGAUTH_CREDIT_STATUS_v1.dirt
          (constraint: native units only, no cross-vendor normalization)

ROLE SPLIT (per c47h STIGALL 2026-04-24 1043, Nugget 3)
-------------------------------------------------------
Two readers exist against `ide_cost_ledger.jsonl`. They are NOT
duplicates; they serve different consumers:

  PRODUCTION (Alice's live prompt, ALREADY WIRED):
      System/swarm_ide_telemetry.summary_for_alice
      - Aggregates per (surface, unit) — sums quantities within a
        single native unit, across agents on that surface.
      - Wired into Applications/sifta_talk_to_alice_widget
        ::_current_system_prompt() since C55M Event 55 (2026-04-24).

  DIAGNOSTIC (this module, NOT WIRED into the live prompt):
      System.swarm_alice_doctor_cost_summary.render_summary
      - Keeps each (surface, agent_id, source_unit) as a SEPARATE
        bullet — finer granularity, no within-unit summing.
      - Use this when an Architect or peer agent asks "WHY does
        Alice see number X?" and needs per-agent attribution.
      - Safe to call from the CLI:
            python3 System/swarm_alice_doctor_cost_summary.py

Both readers honor C55M's Clause-4 boundary: tokens, percent_quota,
credits, watts, and USD are never summed across vendors.

What this module IS
-------------------
A pure, read-only aggregator that turns the heterogeneous rows of
`ide_cost_ledger.jsonl` into a compact summary line. One bullet per
(surface, agent, unit) tuple, each in its own native unit, with the
most recent observation first.

What this module IS NOT (explicit non-claims)
---------------------------------------------
* It does NOT sum or normalize across vendors. There is no aggregate
  USD total, no aggregate token total, no "total cost" line. Per
  C55M's hard rule: "Do not claim 1 Cursor token == 1 Codex token
  == 1 Gemini token."
* It does NOT call vendor APIs.
* It does NOT mutate any file.
* It does NOT speculate about cost when a row is `local_watts`
  with `observed_quantity=0.0` (placeholder until SMC sample lands).

Surface order
-------------
Surfaces are emitted in a stable display order so Alice's prompt
diffs cleanly across cycles:

    cursor → antigravity → codex → alice_local
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

LEDGER_PATH = Path(".sifta_state") / "ide_cost_ledger.jsonl"

SURFACE_DISPLAY_ORDER: Tuple[str, ...] = (
    "cursor",
    "antigravity",
    "codex",
    "alice_local",
)


@dataclass
class SurfaceSummary:
    """Most-recent native-unit reading per (surface, agent_id, source_unit)."""

    surface: str
    agent_id: str
    model_label: str
    plan_name: str
    source_unit: str
    observed_quantity: float
    included_usage_remaining: Optional[float]
    on_demand_limit_usd: Optional[float]
    evidence_kind: str
    sampled_at: float

    def render_line(self) -> str:
        bits: List[str] = []
        bits.append(f"{self.agent_id}@{self.surface}")
        bits.append(self.model_label)
        # Native-unit observation (NO cross-vendor conversion)
        qty = self._fmt_qty(self.observed_quantity)
        bits.append(f"{qty} {self.source_unit}")
        if self.included_usage_remaining is not None:
            head = self._fmt_qty(self.included_usage_remaining)
            unit = self.source_unit if self.source_unit != "tokens" else "headroom"
            bits.append(f"({head} {unit} left)")
        if self.on_demand_limit_usd is not None:
            bits.append(f"on-demand cap ${self._fmt_qty(self.on_demand_limit_usd)}")
        bits.append(f"[{self.evidence_kind}]")
        return " · ".join(bits)

    @staticmethod
    def _fmt_qty(x: float) -> str:
        if x >= 1_000_000:
            return f"{x/1_000_000:.1f}M"
        if x >= 1_000:
            return f"{x/1_000:.1f}K"
        if x == int(x):
            return str(int(x))
        return f"{x:.2f}"


@dataclass
class DoctorCostReport:
    """Aggregated, native-unit-preserving snapshot. No false equivalence."""

    surfaces: List[SurfaceSummary] = field(default_factory=list)
    rows_read: int = 0
    ledger_path: Optional[str] = None
    sampled_at: float = field(default_factory=time.time)

    def render_summary(self) -> str:
        if not self.surfaces:
            return (
                "doctors active: ledger empty — no STIGAUTH cost samples yet. "
                "Each IDE seat must call swarm_ide_cost_ledger.append_sample() "
                "to surface its native-unit metabolism here."
            )
        lines = ["doctors active (native units, no cross-vendor sum):"]
        for s in self.surfaces:
            lines.append(f"  · {s.render_line()}")
        lines.append(
            f"  ({self.rows_read} rows read; cross-vendor totals deliberately omitted "
            f"per C55M Clause-4 boundary)"
        )
        return "\n".join(lines)


def _read_rows(ledger_path: Path) -> List[Dict]:
    if not ledger_path.exists():
        return []
    rows: List[Dict] = []
    with ledger_path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _latest_per_key(rows: List[Dict]) -> List[SurfaceSummary]:
    """Keep only the most-recent row per (surface, agent_id, source_unit).

    Two readings of the same (surface, agent, unit) are treated as superseding.
    Two readings of the SAME surface+agent in DIFFERENT units are both kept
    (e.g. Cursor C47H in `percent_quota` and `tokens` are both legitimate
    facets of one observation).
    """
    latest: Dict[Tuple[str, str, str], Dict] = {}
    for row in rows:
        if row.get("event") != "ide_cost_sample":
            continue
        try:
            key = (row["surface"], row["agent_id"], row["source_unit"])
        except KeyError:
            continue
        existing = latest.get(key)
        if existing is None or row.get("sampled_at", 0) >= existing.get("sampled_at", 0):
            latest[key] = row
    summaries: List[SurfaceSummary] = []
    for row in latest.values():
        try:
            summaries.append(
                SurfaceSummary(
                    surface=row["surface"],
                    agent_id=row["agent_id"],
                    model_label=row["model_label"],
                    plan_name=row.get("plan_name", ""),
                    source_unit=row["source_unit"],
                    observed_quantity=float(row["observed_quantity"]),
                    included_usage_remaining=row.get("included_usage_remaining"),
                    on_demand_limit_usd=row.get("on_demand_limit_usd"),
                    evidence_kind=row.get("evidence_kind", "unknown"),
                    sampled_at=float(row.get("sampled_at", 0.0)),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    summaries.sort(
        key=lambda s: (
            SURFACE_DISPLAY_ORDER.index(s.surface)
            if s.surface in SURFACE_DISPLAY_ORDER
            else len(SURFACE_DISPLAY_ORDER),
            s.agent_id,
            s.source_unit,
        )
    )
    return summaries


def build_report(
    *, ledger_path: Optional[Path] = None
) -> DoctorCostReport:
    """Read the cost ledger and assemble a native-unit summary report."""
    target = Path(ledger_path) if ledger_path else LEDGER_PATH
    rows = _read_rows(target)
    summaries = _latest_per_key(rows)
    return DoctorCostReport(
        surfaces=summaries,
        rows_read=len(rows),
        ledger_path=str(target),
    )


def render_summary(*, ledger_path: Optional[Path] = None) -> str:
    """One-call helper for the composite-identity prompt builder."""
    return build_report(ledger_path=ledger_path).render_summary()


if __name__ == "__main__":
    print(render_summary())
