#!/usr/bin/env python3
"""POWER MAX stack — all profit organs in one we-code-together package (r1662).

Owner: CODE WITH GROK + CODEX in We Code Together. Same up. Multiple IDEs.

Stack (import these — do not reinvent):
  1. alice_15m_co_direction     — best 1–3 same field direction
  2. kalshi_pro_tape_dirt       — liquidity / lottery sit
  3. alice_usd_take_profit      — fee-true green cash-out API
  4. xrp_favorite_exit_plan     — 90%+ coupon math
  5. alice_15m_scalp_learner    — STGM virtual scalps
  6. alice_prediction_market_awareness — Alice knows her app
  7. kalshi_usd_hand            — dual US$ under caps when owner arms
  8. sifta_the_climb            — evidence ladder (no reckless size)

Truth: ALICE_POWER_MAX_STACK_V1
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
STATE = ROOT / ".sifta_state"
TRUTH = "ALICE_POWER_MAX_STACK_V1"
STATUS = "alice_power_max_status.json"
STATUS_MD = "alice_power_max_status.md"
RECEIPT = "r1662-power-max-we-code-together"


def _state(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else p / ".sifta_state"


def stack_manifest() -> dict[str, Any]:
    return {
        "truth_label": TRUTH,
        "receipt_id": RECEIPT,
        "owner_phrase": "BUY WELL + TAKE PROFITS — co-dir cluster — liquid 15m only",
        "modules": [
            {
                "id": "co_direction",
                "path": "System/alice_15m_co_direction.py",
                "role": "Pick 1–3 tickers same majority direction; contrarians last/skip",
            },
            {
                "id": "pro_tape",
                "path": "System/kalshi_pro_tape_dirt.py",
                "role": "5min/24h liquidity score; lottery premium sit",
            },
            {
                "id": "take_profit",
                "path": "System/alice_usd_take_profit.py",
                "role": "Live reduce_only cash-out when fee-true green ≥ $0.03",
            },
            {
                "id": "favorite_exit",
                "path": "System/xrp_favorite_exit_plan.py",
                "role": "90%+ coupon BE-WR + flip simulator; preserve capital",
            },
            {
                "id": "scalp_stgm",
                "path": "System/alice_15m_scalp_learner.py",
                "role": "Paper/STGM fee-true virtual scalps + hold CF",
            },
            {
                "id": "awareness",
                "path": "System/alice_prediction_market_awareness.py",
                "role": "Alice knows Predictions app + cash + climb",
            },
            {
                "id": "usd_hand",
                "path": "System/kalshi_usd_hand.py",
                "role": "Dual US$ when owner arms (button / GO)",
            },
            {
                "id": "climb",
                "path": "System/sifta_the_climb.py",
                "role": "Evidence ladder — no auto 100k recklessness",
            },
            {
                "id": "fee_net_tournament",
                "path": "System/alice_fee_net_tournament.py",
                "role": "r1667 fee-net shadow cohorts + policy-hash interlock; live best1",
            },
        ],
        "caps": {"max_open": 1, "max_same_dir": 1, "band": [0.70, 0.88], "entry_max_secs": 420},
        "rules": [
            "Buy at minute ≤7 left (not 11) · 70–88 · Rainman · co-dir · liquid · not lottery",
            "LIVE: one best co-dir ticker (minute7_best1) — owner streak",
            "SHADOW: pair + minute-5 single for fee-net science",
            "Optimize fee-net EV not raw WR (74.9% WR still lost units)",
            "TP: fee-true net ≥ $0.03 reduce_only",
            "US$ OFF during r1667 tournament until promote gates",
            "Policy-hash mismatch → no new tickets",
        ],
        "for_codex": (
            "POWER MAX + r1667 fee-net tournament. "
            "Import alice_fee_net_tournament.publish_we_code / bootstrap_report. "
            "Live=minute7_best1. Shadow=minute7_best2+minute5_best1. "
            "Do not fork pickers. Same up — Grok + Codex + Alice."
        ),
        "for_alice": (
            "I bet one best co-direction ticker at a time. "
            "I shadow the pair for science. Fee-net EV over win rate. "
            "US$ off until owner promotes a cohort."
        ),
    }


def publish(*, state_dir: Optional[Path | str] = None, network: bool = True) -> dict[str, Any]:
    """One status for glass / Codex / owner."""
    root = _state(state_dir)
    root.mkdir(parents=True, exist_ok=True)
    man = stack_manifest()
    out: dict[str, Any] = {
        **man,
        "ts": time.time(),
        "stamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    try:
        from System.alice_15m_co_direction import board_field

        f = board_field(state_dir=root)
        out["co_direction"] = {
            "field": f.get("label"),
            "clear": f.get("field_clear"),
            "best3": f.get("best3"),
            "avoid": f.get("avoid"),
            "frac": f.get("majority_frac"),
        }
    except Exception as exc:
        out["co_direction"] = {"error": f"{type(exc).__name__}:{exc}"}
    try:
        from System.kalshi_usd_hand import status_line, load_night

        out["usd"] = {
            "status": status_line(root),
            "open": [
                {"asset": o.get("asset"), "side": o.get("side"), "price": o.get("price")}
                for o in (load_night(root).get("open") or [])
            ],
            "realized": load_night(root).get("realized_pnl_usd"),
        }
    except Exception as exc:
        out["usd"] = {"error": f"{type(exc).__name__}:{exc}"}
    if network:
        try:
            from System.kalshi_portfolio_read import fetch_balance

            b = fetch_balance()
            out["cash_usd"] = b.get("balance_usd") if b.get("ok") else None
        except Exception:
            out["cash_usd"] = None
    try:
        from System.alice_prediction_market_awareness import publish as pub_aware

        aware = pub_aware(state_dir=root, network=network)
        out["awareness"] = aware.get("first_person")
    except Exception as exc:
        out["awareness"] = f"error:{exc}"
    try:
        from System.sifta_the_climb import evaluate

        e = evaluate()
        out["climb"] = {
            "rung": e.get("current_rung"),
            "fills": (e.get("gates_to_next") or {}).get("fills"),
            "ev": (e.get("gates_to_next") or {}).get("ev"),
            "promote": e.get("promotion_earned"),
        }
    except Exception as exc:
        out["climb"] = {"error": f"{type(exc).__name__}:{exc}"}
    try:
        from System.alice_fee_net_tournament import (
            bootstrap_report,
            load_config,
            running_policy_hash,
        )

        out["fee_net"] = {
            "policy_hash": running_policy_hash(),
            "config": {
                k: load_config(state_dir=root).get(k)
                for k in ("epoch_active", "usd_shadow_only", "live_cohort", "live_max_open")
            },
            "report": bootstrap_report(state_dir=root).get("promote_gates"),
        }
    except Exception as exc:
        out["fee_net"] = {"error": f"{type(exc).__name__}:{exc}"}

    (root / STATUS).write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    md = [
        f"# POWER MAX · {out.get('stamp')}",
        "",
        man["for_alice"],
        "",
        f"- USD: `{(out.get('usd') or {}).get('status')}`",
        f"- Cash: `{out.get('cash_usd')}`",
        f"- Field: `{(out.get('co_direction') or {}).get('field')}` best3=`{(out.get('co_direction') or {}).get('best3')}` avoid=`{(out.get('co_direction') or {}).get('avoid')}`",
        f"- Climb: `{out.get('climb')}`",
        "",
        "## Modules",
        *[f"- **{m['id']}**: `{m['path']}` — {m['role']}" for m in man["modules"]],
        "",
        "## Codex",
        man["for_codex"],
        "",
        "## Rules",
        *[f"- {r}" for r in man["rules"]],
        "",
    ]
    (root / STATUS_MD).write_text("\n".join(md), encoding="utf-8")

    # We Code Together + IDE pheromone for Codex
    try:
        with (root / "we_code_together_coded.jsonl").open("a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "ts": out["ts"],
                        "truth_label": "WE_CODE_TOGETHER_CODED_V1",
                        "family": "alice_power_max_stack",
                        "receipt_id": RECEIPT,
                        "module": "System/alice_power_max_stack.py",
                        "for_codex": man["for_codex"],
                        "for_alice": man["for_alice"],
                        "status": STATUS,
                        "modules": [m["path"] for m in man["modules"]],
                    },
                    sort_keys=True,
                )
                + "\n"
            )
    except OSError:
        pass
    try:
        with (root / "ide_stigmergic_trace.jsonl").open("a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "ts": out["ts"],
                        "event": "power_max_we_code_together",
                        "from": "grok",
                        "to": "codex",
                        "msg": man["for_codex"],
                        "receipt_id": RECEIPT,
                    },
                    sort_keys=True,
                )
                + "\n"
            )
    except OSError:
        pass
    # to-be-coded clean note: stack complete
    try:
        with (root / "we_code_together_to_be_coded.jsonl").open("a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "ts": out["ts"],
                        "title": "POWER MAX profit stack LIVE",
                        "status": "coded",
                        "receipt_id": RECEIPT,
                        "note": "Grok shipped full stack — Codex extend, do not duplicate pickers",
                        "truth_label": "WE_CODE_TOGETHER_TO_BE_CODED_V1",
                    },
                    sort_keys=True,
                )
                + "\n"
            )
    except OSError:
        pass
    return out


if __name__ == "__main__":
    s = publish(network=True)
    print(json.dumps({k: s.get(k) for k in ("stamp", "usd", "cash_usd", "co_direction", "climb")}, indent=2, default=str))
    print((s.get("awareness") or "")[:400])
