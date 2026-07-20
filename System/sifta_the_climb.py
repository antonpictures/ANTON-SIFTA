#!/usr/bin/env python3
"""THE CLIMB — exchange-receipted, evidence-gated USD sizing ladder.

This organ recommends only.  It has no order path and no sizing authority.
Promotion uses Alice-linked Kalshi fill IDs joined to exchange settlements,
after exact fees.  Account-wide 15m settlements and the local paper ledger
are deliberately ineligible because they can include unrelated trades or an
incorrect NO-side premium.
"""

from __future__ import annotations

import json
import math
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
STATE = ROOT / ".sifta_state"

TRUTH_LABEL = "SIFTA_THE_CLIMB_V2_EXCHANGE_RECEIPTED"
OUT_JSON_NAME = "alice_climb.json"
OUT_MD_NAME = "alice_climb.md"

MIN_FILLS_PER_RUNG = 100
EV_GATE_USD = 0.05
BANKROLL_FRACTION = 0.10
TICKETS_PER_NIGHT_EST = 20
LANE_MAX_CONTRACTS = 20
Z_95 = 1.96

RUNGS = [
    {"rung": 0, "contracts": 1},
    {"rung": 1, "contracts": 2},
    {"rung": 2, "contracts": 5},
    {"rung": 3, "contracts": 10},
    {"rung": 4, "contracts": LANE_MAX_CONTRACTS},
]

MILESTONES = [20, 50, 100, 500, 1_000, 10_000, 100_000]


def _state(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else p / ".sifta_state"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _finite(value: Any) -> Optional[float]:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _bankroll(state_dir: Optional[Path | str] = None) -> Optional[float]:
    return _finite(_read_json(_state(state_dir) / "kalshi_portfolio_cache.json").get("balance_usd"))


def _lower_95(values: list[float]) -> Optional[float]:
    """Normal-approximation lower confidence bound; unavailable for n < 2."""
    n = len(values)
    if n < 2:
        return None
    mean = sum(values) / n
    sample_var = sum((v - mean) ** 2 for v in values) / (n - 1)
    return round(mean - Z_95 * math.sqrt(sample_var / n), 6)


def _campaign_graded(
    *, state_dir: Optional[Path | str] = None
) -> dict[str, Any]:
    """Read only strict Alice-order exchange reconciliation from the cache."""
    root = _state(state_dir)
    cache = _read_json(root / "kalshi_portfolio_cache.json")
    rec = cache.get("exchange_reconciliation")
    rec = rec if isinstance(rec, dict) else {}
    raw_rows = rec.get("rows")
    raw_rows = raw_rows if isinstance(raw_rows, list) else []
    rows: list[dict[str, Any]] = []
    pnls: list[float] = []
    counts: list[float] = []
    for raw in raw_rows:
        if not isinstance(raw, dict):
            continue
        pnl = _finite(raw.get("pnl_usd"))
        if pnl is None:
            continue
        rows.append(raw)
        pnls.append(pnl)
        count = _finite(raw.get("count"))
        if count is not None and count > 0:
            counts.append(count)

    n = len(pnls)
    total = round(sum(pnls), 6)
    ev = round(total / n, 6) if n else None
    history_ts = _finite(cache.get("history_ts"))
    stale_after = _finite(cache.get("history_stale_after_seconds")) or 90.0
    history_age = max(0.0, time.time() - history_ts) if history_ts is not None else None
    known = bool(rec) and history_ts is not None
    fresh = bool(known and history_age is not None and history_age <= stale_after)
    complete = bool(rec.get("complete"))
    return {
        "n_graded_settles": n,
        "wins": sum(1 for row in rows if row.get("won") is True),
        "losses": sum(1 for row in rows if row.get("won") is False),
        "total_realized_usd": total,
        "live_ev_per_ticket": ev,
        "ev_lower_95": _lower_95(pnls),
        "source": rec.get("source") or "alice_order_id_exchange_reconciliation",
        "history_known": known,
        "history_fresh": fresh,
        "history_age_seconds": history_age,
        "reconciliation_complete": complete,
        "missing_exchange_fills": int(rec.get("n_local_orders_missing_exchange_fill") or 0),
        "unsettled_exchange_fills": int(rec.get("n_unsettled_fills") or 0),
        "capacity_proven_contracts": max(counts) if counts else 0.0,
        "rows": rows,
    }


def evaluate(
    audit_data: Optional[dict[str, Any]] = None,
    *,
    exchange_truth: Optional[dict[str, Any]] = None,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Return current ladder evidence. ``exchange_truth`` is compatibility-only.

    Broad account settlement summaries are intentionally ignored.  The only
    eligible source is the Alice order-ID reconciliation in portfolio cache.
    """
    del exchange_truth
    campaign = _campaign_graded(state_dir=state_dir)
    if audit_data is None:
        try:
            from System.kalshi_usd_audit import audit

            audit_data = audit(state_dir=_state(state_dir))
        except Exception:
            audit_data = {}
    audit_data = audit_data or {}

    n = int(campaign.get("n_graded_settles") or 0)
    ev = _finite(campaign.get("live_ev_per_ticket"))
    lower = _finite(campaign.get("ev_lower_95"))
    bankroll = _bankroll(state_dir)
    current_rung = RUNGS[0]
    next_rung = RUNGS[1]
    next_stake = float(next_rung["contracts"]) * 0.84
    audit_findings = audit_data.get("findings") or []
    audit_fail = audit_data.get("verdict") == "FAIL" or any(
        isinstance(row, dict) and row.get("level") == "FAIL" for row in audit_findings
    )
    capacity = float(campaign.get("capacity_proven_contracts") or 0.0)

    gates = {
        "fills": f"{n}/{MIN_FILLS_PER_RUNG}",
        "fills_ok": n >= MIN_FILLS_PER_RUNG,
        "ev": ev,
        "ev_ok": ev is not None and ev >= EV_GATE_USD,
        "ev_gate": EV_GATE_USD,
        "ev_lower_95": lower,
        "confidence_ok": lower is not None and lower > 0.0,
        "wins": campaign.get("wins"),
        "losses": campaign.get("losses"),
        "total_realized_usd": campaign.get("total_realized_usd"),
        "pnl_source": campaign.get("source"),
        "exchange_history_known": bool(campaign.get("history_known")),
        "exchange_history_fresh": bool(campaign.get("history_fresh")),
        "exchange_history_age_seconds": campaign.get("history_age_seconds"),
        "exchange_reconciliation_complete": bool(campaign.get("reconciliation_complete")),
        "missing_exchange_fills": int(campaign.get("missing_exchange_fills") or 0),
        "unsettled_exchange_fills": int(campaign.get("unsettled_exchange_fills") or 0),
        "exchange_truth_ok": bool(
            campaign.get("history_known")
            and campaign.get("history_fresh")
            and campaign.get("reconciliation_complete")
        ),
        "policy_audit_verdict": audit_data.get("verdict") or "UNKNOWN",
        "policy_audit_ok": not audit_fail and bool(audit_data),
        "postdeal_graded": audit_data.get("n_graded_settles"),
        "capacity_proven_contracts": capacity,
        "capacity_needed_contracts": next_rung["contracts"],
        "capacity_ok": capacity + 1e-9 >= float(next_rung["contracts"]),
        "bankroll_ok": bankroll is not None and next_stake <= bankroll * BANKROLL_FRACTION,
        "bankroll_needed_for_next": round(next_stake / BANKROLL_FRACTION, 2),
    }
    promote = all(
        bool(gates[key])
        for key in (
            "fills_ok",
            "ev_ok",
            "confidence_ok",
            "exchange_truth_ok",
            "policy_audit_ok",
            "capacity_ok",
            "bankroll_ok",
        )
    )
    return {
        "truth_label": TRUTH_LABEL,
        "ts": time.time(),
        "current_rung": current_rung["rung"],
        "current_contracts": current_rung["contracts"],
        "bankroll_usd": bankroll,
        "gates_to_next": gates,
        "promotion_earned": promote,
        "lane_max_contracts": LANE_MAX_CONTRACTS,
        "owner_go_required": True,
        "note": (
            "recommendation only; no automatic sizing; strict Alice order-ID exchange "
            "receipts only; owner must arm every rung"
        ),
    }


def project(
    ev_per_ticket: float,
    contracts: int,
    bankroll: float,
    tickets_per_night: int = TICKETS_PER_NIGHT_EST,
) -> dict[str, Any]:
    """Expectation math only; callers must gate on promotion evidence first."""
    nightly = round(ev_per_ticket * contracts * tickets_per_night, 2)
    horizons: dict[str, str] = {}
    if nightly > 0:
        for milestone in MILESTONES:
            if milestone <= bankroll:
                continue
            horizons[f"${milestone:,}"] = f"~{math.ceil((milestone - bankroll) / nightly)} nights"
    ceiling_nightly = round(ev_per_ticket * LANE_MAX_CONTRACTS * tickets_per_night, 2)
    return {
        "nightly_expectation_usd": nightly,
        "milestone_horizons": horizons,
        "lane_ceiling_nightly_usd": ceiling_nightly,
        "ceiling_note": (
            f"This lane is capped near {LANE_MAX_CONTRACTS} contracts/ticket; larger "
            "size requires separately observed liquidity and slippage evidence."
        ),
    }


def write_report(
    exchange_truth: Optional[dict[str, Any]] = None,
    *,
    state_dir: Optional[Path | str] = None,
) -> Path:
    root = _state(state_dir)
    root.mkdir(parents=True, exist_ok=True)
    result = evaluate(exchange_truth=exchange_truth, state_dir=root)
    gates = result["gates_to_next"]
    bankroll = result["bankroll_usd"] or 0.0
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ev = gates.get("ev")
    lower = gates.get("ev_lower_95")
    lines = [
        "# THE CLIMB — exchange-receipted ladder (recommendation only)",
        f"updated {stamp}",
        "",
        f"- **RUNG {result['current_rung']}** · {result['current_contracts']} contract/ticket",
        f"- cash ${bankroll:.2f} · Alice-linked exchange fills {gates['fills']}",
        f"- fee-net EV {ev if ev is not None else 'n/a'} · 95% lower bound {lower if lower is not None else 'n/a'}",
        f"- source `{gates['pnl_source']}`",
        f"- **promotion earned: {result['promotion_earned']}** · owner GO still required",
        "",
        "## Gates to RUNG 1 (2 contracts)",
        f"- fills ≥ {MIN_FILLS_PER_RUNG}: {'✓' if gates['fills_ok'] else '✗'}",
        f"- EV ≥ +{EV_GATE_USD}: {'✓' if gates['ev_ok'] else '✗'}",
        f"- 95% EV floor > 0: {'✓' if gates['confidence_ok'] else '✗'}",
        f"- exchange history fresh + complete: {'✓' if gates['exchange_truth_ok'] else '✗'}",
        f"- policy audit: {gates['policy_audit_verdict']} {'✓' if gates['policy_audit_ok'] else '✗'}",
        f"- capacity observed {gates['capacity_proven_contracts']:g}/{gates['capacity_needed_contracts']} ct: {'✓' if gates['capacity_ok'] else '✗'}",
        f"- bankroll ≥ ${gates['bankroll_needed_for_next']:.2f}: {'✓' if gates['bankroll_ok'] else '✗'}",
        "",
    ]
    if result["promotion_earned"] and ev is not None and ev > 0:
        p = project(ev, result["current_contracts"], bankroll)
        lines.extend(
            [
                "## Conditional projection (all evidence gates passed)",
                f"- expected value at current sizing: ${p['nightly_expectation_usd']:.2f}/night",
                f"- {p['ceiling_note']}",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "## Projection",
                "- blocked: no money-growth projection is honest until every gate passes.",
                "",
            ]
        )
    lines.append("USD remains owner-armed · STGM curriculum may run while USD is halted.")
    md_path = root / OUT_MD_NAME
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    (root / OUT_JSON_NAME).write_text(
        json.dumps(result, indent=2, default=str), encoding="utf-8"
    )
    return md_path


if __name__ == "__main__":
    path = write_report()
    print(path.read_text(encoding="utf-8"))
