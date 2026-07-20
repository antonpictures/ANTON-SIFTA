#!/usr/bin/env python3
"""Robinhood as shadow retail-attention proxy for Kalshi 15m (r1680).

Owner photos: RH BTC live next to Kalshi BTC 15m. Not a truth source.
Kalshi settles on CF Benchmarks RTI — Robinhood is a different print.

Rules:
  • Shadow / research only — never arms USD or changes the live picker
  • Point-in-time rows only (no hindsight relabel of past settles)
  • Promote only if fee-net EV CI95 lower > 0 on reserved holdout windows

Truth: ALICE_ROBINHOOD_SHADOW_SIGNAL_V1
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".sifta_state"
TRUTH = "ALICE_ROBINHOOD_SHADOW_SIGNAL_V1"
RECEIPT = "r1680-robinhood-shadow-signal"
LOG_NAME = "alice_robinhood_shadow.jsonl"
STATUS_NAME = "alice_robinhood_shadow_status.json"

# Holdout: first N independent windows after activation stay unscored for promotion
HOLDOUT_WINDOWS = 100


def _state(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else p / ".sifta_state"


def _append(row: dict[str, Any], *, state_dir: Path) -> None:
    path = state_dir / LOG_NAME
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, sort_keys=True, default=str) + "\n")


def record_paired_snapshot(
    *,
    asset: str,
    rh_price: float,
    kalshi_yes: Optional[float] = None,
    kalshi_target: Optional[float] = None,
    kalshi_now: Optional[float] = None,
    kalshi_secs_left: Optional[float] = None,
    kalshi_ticker: str = "",
    source: str = "manual_or_scrape",
    state_dir: Optional[Path | str] = None,
    notes: str = "",
) -> dict[str, Any]:
    """Freeze one RH + Kalshi observation at the same wall clock (point-in-time)."""
    root = _state(state_dir)
    root.mkdir(parents=True, exist_ok=True)
    now = time.time()
    a = str(asset or "BTC").upper()
    rh = float(rh_price)
    row: dict[str, Any] = {
        "truth_label": TRUTH,
        "receipt_id": RECEIPT,
        "event": "rh_kalshi_paired_snapshot",
        "ts": now,
        "stamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "asset": a,
        "rh_price": rh,
        "kalshi_yes": kalshi_yes,
        "kalshi_target": kalshi_target,
        "kalshi_now": kalshi_now,
        "kalshi_secs_left": kalshi_secs_left,
        "kalshi_ticker": kalshi_ticker,
        "source": source,
        "notes": notes[:400],
        "live_effect": "none",
        "usd_effect": "none",
        "hindsight": False,
        "hypothesis": (
            "Robinhood retail print may lead or lag Kalshi 15m mids; "
            "test fee-net EV on holdout only"
        ),
    }
    # Distances (spot proxies — RTI may differ from RH)
    if kalshi_target is not None and rh > 0:
        row["rh_minus_target"] = round(rh - float(kalshi_target), 4)
        row["rh_vs_target_side"] = "above" if rh >= float(kalshi_target) else "below"
    if kalshi_now is not None and rh > 0:
        row["rh_minus_kalshi_now"] = round(rh - float(kalshi_now), 4)
    if kalshi_yes is not None:
        try:
            ky = float(kalshi_yes)
            row["kalshi_fav"] = round(max(ky, 1.0 - ky), 4)
            row["kalshi_side"] = "yes" if ky >= 0.5 else "no"
        except (TypeError, ValueError):
            pass

    _append(row, state_dir=root)
    status = {
        "truth_label": TRUTH,
        "receipt_id": RECEIPT,
        "ts": now,
        "last": {
            k: row.get(k)
            for k in (
                "asset",
                "rh_price",
                "kalshi_yes",
                "kalshi_target",
                "kalshi_now",
                "rh_minus_target",
                "stamp",
            )
        },
        "rules": [
            "shadow only — not an oracle",
            "same-resolution timestamps required for lead/lag tests",
            f"holdout first {HOLDOUT_WINDOWS} windows unscored for promotion",
            "reject if fee-net CI95 lower ≤ 0 or signal dies without hindsight",
        ],
        "live_picker": "untouched",
    }
    (root / STATUS_NAME).write_text(json.dumps(status, indent=2), encoding="utf-8")
    return row


def record_from_kalshi_live_plus_rh(
    rh_price: float,
    *,
    asset: str = "BTC",
    state_dir: Optional[Path | str] = None,
    notes: str = "",
) -> dict[str, Any]:
    """Pair a manual/scraped RH price with current kalshi_15m_live.json row."""
    root = _state(state_dir)
    path = root / "kalshi_15m_live.json"
    ky = target = snow = secs = None
    ticker = ""
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            for m in data.get("markets") or []:
                if str(m.get("asset") or "").upper() != str(asset).upper():
                    continue
                ky = m.get("kalshi_yes")
                if ky is None:
                    ky = m.get("yes_price")
                target = m.get("target_price")
                snow = m.get("spot") or m.get("underlying") or m.get("index_price")
                # often "now" is not in strip — leave None
                secs = m.get("seconds_to_close")
                ticker = str(m.get("kalshi_ticker") or m.get("ticker") or "")
                break
        except Exception:
            pass
    return record_paired_snapshot(
        asset=asset,
        rh_price=rh_price,
        kalshi_yes=float(ky) if ky is not None else None,
        kalshi_target=float(target) if target is not None else None,
        kalshi_now=float(snow) if snow is not None else None,
        kalshi_secs_left=float(secs) if secs is not None else None,
        kalshi_ticker=ticker,
        source="rh_manual_plus_kalshi_live",
        state_dir=root,
        notes=notes,
    )


def shadow_manifest() -> dict[str, Any]:
    return {
        "truth_label": TRUTH,
        "receipt_id": RECEIPT,
        "role": "retail_attention_proxy",
        "not": "kalshi_settlement_oracle",
        "settlement_truth": "CF Benchmarks RTI on Kalshi 15m crypto",
        "tests_required": [
            "synchronized timestamps RH vs Kalshi mid/target",
            "lead/lag cross-correlation out of sample",
            "fee-net EV lift vs baseline minute7_best1",
            "holdout fee-net CI95 lower > 0",
            "reject if only works with hindsight or tiny n",
        ],
        "live_use": "forbidden_until_promote",
        "for_codex": (
            "r1680 Robinhood shadow signal scaffold. "
            "record_paired_snapshot / record_from_kalshi_live_plus_rh. "
            "Log: alice_robinhood_shadow.jsonl. Do not wire into picker."
        ),
    }


if __name__ == "__main__":
    print(json.dumps(shadow_manifest(), indent=2))
