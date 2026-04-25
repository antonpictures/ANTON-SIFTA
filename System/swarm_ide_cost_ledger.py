"""
System/swarm_ide_cost_ledger.py

Canonical writer for `.sifta_state/ide_cost_ledger.jsonl`.

Authored: c47h (claude-opus-4-7-thinking-high, Cursor seat, M5)
Per:      C55M / Dr. Codex drop
          Archive/c47h_drops_pending_review/
              C55M_drop_TRIPLE_IDE_STIGAUTH_CREDIT_STATUS_v1.dirt

Doctrine
--------
STIGAUTH (work / identity / verdict) and vendor credits (billing) are
**different ledgers**. Do not normalize across vendors here. Record the
raw observed quantity in the unit it was measured in. Cross-IDE comparison
is the consumer's job, not this ledger's.

Hard rules:
  * No conversion between unit systems on write.
  * Every row carries an `evidence_kind` and `evidence_ref` so a future
    auditor can trace where the number came from (dashboard screenshot,
    CSV export, vendor API, local process sample, manual receipt).
  * Schema is registered in `System/canonical_schemas.py` so the
    oncology macrophage will not flag this file as a tumor (per the
    Codex [O1] whitelist-inversion fix).

Non-claims:
  * Does not call vendor APIs.
  * Does not aggregate, sum, or normalize across rows.
  * Does not assert dollar conversion for non-USD units.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from System.jsonl_file_lock import append_line_locked
from System.canonical_schemas import assert_payload_keys

LEDGER_NAME = "ide_cost_ledger.jsonl"
SCHEMA_TAG = "SIFTA_IDE_COST_LEDGER_V1"
EVENT_KIND = "ide_cost_sample"

ALLOWED_SURFACES = frozenset({"cursor", "codex", "antigravity", "alice_local"})
ALLOWED_UNITS = frozenset({
    "tokens",
    "requests",
    "messages",
    "credits",
    "usd",
    "local_watts",
    "percent_quota",
    "context_window",
    "metabolic_pathway",
})
ALLOWED_EVIDENCE = frozenset({
    "dashboard_screenshot",
    "csv_export",
    "vendor_api",
    "local_process_sample",
    "manual_receipt",
    "architect_statement",
})
ALLOWED_STIGAUTH = frozenset({"STIGAUTH_ACTIVE", "STIGAUTH_STANDBY", "UNKNOWN"})


def _default_ledger_path() -> Path:
    return Path(".sifta_state") / LEDGER_NAME


@dataclass
class IDECostSample:
    """One observation of vendor cost / IDE metabolism, in native units."""

    surface: str
    agent_id: str
    model_label: str
    plan_name: str
    source_unit: str
    observed_quantity: float
    evidence_kind: str
    evidence_ref: str
    observed_cost_usd: float = 0.0
    included_usage_remaining: Optional[float] = None
    on_demand_limit_usd: Optional[float] = None
    stigauth_status: str = "UNKNOWN"
    sampled_at: float = field(default_factory=time.time)

    def validate(self) -> None:
        if self.surface not in ALLOWED_SURFACES:
            raise ValueError(
                f"surface={self.surface!r} not in {sorted(ALLOWED_SURFACES)}"
            )
        if self.source_unit not in ALLOWED_UNITS:
            raise ValueError(
                f"source_unit={self.source_unit!r} not in {sorted(ALLOWED_UNITS)}"
            )
        if self.evidence_kind not in ALLOWED_EVIDENCE:
            raise ValueError(
                f"evidence_kind={self.evidence_kind!r} not in {sorted(ALLOWED_EVIDENCE)}"
            )
        if self.stigauth_status not in ALLOWED_STIGAUTH:
            raise ValueError(
                f"stigauth_status={self.stigauth_status!r} not in {sorted(ALLOWED_STIGAUTH)}"
            )
        if self.observed_quantity < 0:
            raise ValueError("observed_quantity must be >= 0")
        if self.observed_cost_usd < 0:
            raise ValueError("observed_cost_usd must be >= 0")
        if not self.agent_id or not self.model_label:
            raise ValueError("agent_id and model_label are required")
        if not self.evidence_ref:
            raise ValueError(
                "evidence_ref required — every row must point back to its source"
            )

    def to_payload(self, *, write_ts: Optional[float] = None) -> Dict[str, Any]:
        self.validate()
        ts = write_ts if write_ts is not None else self.sampled_at
        return {
            "event": EVENT_KIND,
            "schema": SCHEMA_TAG,
            "surface": self.surface,
            "agent_id": self.agent_id,
            "model_label": self.model_label,
            "plan_name": self.plan_name,
            "source_unit": self.source_unit,
            "observed_quantity": float(self.observed_quantity),
            "observed_cost_usd": float(self.observed_cost_usd),
            "included_usage_remaining": self.included_usage_remaining,
            "on_demand_limit_usd": self.on_demand_limit_usd,
            "evidence_kind": self.evidence_kind,
            "evidence_ref": self.evidence_ref,
            "stigauth_status": self.stigauth_status,
            "sampled_at": float(self.sampled_at),
            "ts": float(ts),
        }


def append_sample(
    sample: IDECostSample,
    *,
    ledger_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Append one validated sample row to the ledger. Returns the row dict."""
    payload = sample.to_payload()
    assert_payload_keys(LEDGER_NAME, payload, strict=True)
    target = Path(ledger_path) if ledger_path else _default_ledger_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    # F14 discipline (Chapter IV): caller of append_line_locked owns the
    # trailing newline. Concatenated rows = unparseable ledger.
    append_line_locked(target, json.dumps(payload, ensure_ascii=False) + "\n")
    return payload


def append_many(
    samples: List[IDECostSample],
    *,
    ledger_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    return [append_sample(s, ledger_path=ledger_path) for s in samples]


if __name__ == "__main__":
    sample = IDECostSample(
        surface="cursor",
        agent_id="C47H",
        model_label="claude-opus-4-7-thinking-high",
        plan_name="Ultra $200/mo",
        source_unit="percent_quota",
        observed_quantity=31.0,
        evidence_kind="dashboard_screenshot",
        evidence_ref="self_test:smoke",
        stigauth_status="STIGAUTH_ACTIVE",
    )
    payload = sample.to_payload()
    print(json.dumps(payload, indent=2))
