#!/usr/bin/env python3
"""Bounded real-body STGM skin for Alice's 15-minute prediction learner.

This is deliberately not an internal casino or a second currency:

* a settled loss writes one signed canonical ``STGM_SPEND``;
* a verified win earns the existing signed ``verified_execution`` work pulse;
* no escrow, house wallet, synthetic transfer, or unfunded payout is used;
* ticker idempotency, reserve floors, an open-stake cap, and a nightly loss cap
  keep the learning signal real without putting the organism at risk.

Kalshi USD remains OFF.  The public Kalshi API supplies outcomes only.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from pathlib import Path
from typing import Any, Optional

REPO = Path(__file__).resolve().parents[1]
STATE = REPO / ".sifta_state"
REPAIR_LOG = REPO / "repair_log.jsonl"
BUDGET_NAME = "alice_15m_body_stgm_budget.json"
LEDGER_NAME = "alice_15m_body_stgm_ledger.jsonl"

TRUTH = "ALICE_15M_BODY_STGM_V3"
TRUTH_LEGACY = "ALICE_15M_BODY_STGM_V2"  # symmetric ±0.0005 epoch (pre r1629)
POLICY = "PREDICTION_LEARNING_STGM_SKIN_V2_DOLLAR_PARITY"
ORGAN = "prediction_15m"
SOURCE = "alice_15m_body_stgm"
AGENT = "ALICE_M5"

# r1629: 0.0010 STGM ≡ $1. Body PnL mirrors dollar economics (asymmetric).
# Win → +stake × (mult_net − 1); loss → −stake. Old ±0.0005 rows are epoch-fenced.
from System.sifta_15m_money_math import (  # noqa: E402
    STGM_PER_USD,
    net_multiplier,
    stgm_pnl_from_price,
)

STGM_STAKE = STGM_PER_USD  # 0.0010
STGM_WIN_REWARD = STGM_PER_USD  # upper bound label; actual win uses mult
STGM_FLOOR_TOTAL = 1100.0
STGM_FLOOR_M5 = 50.0
# Was 0.05 @ 0.0005/ticket (~100 losses). 2× stake → 0.10 (~100 full $1 losses).
STGM_NIGHT_MAX_LOSS = 0.10
# Was 0.01 = 20 × 0.0005. Keep ~10 concurrent dollar-parity tickets.
STGM_MAX_OPEN = 0.05  # r1710: room for multi concurrent STGM paper learning stakes
STAKE_EPOCH = "dollar_parity_v1"  # r1629 asymmetric economics


def _state_dir(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return STATE
    path = Path(state_dir)
    return path if path.name == ".sifta_state" else path / ".sifta_state"


def _budget_path(state_dir: Optional[Path | str] = None) -> Path:
    return _state_dir(state_dir) / BUDGET_NAME


def _ledger_path(state_dir: Optional[Path | str] = None) -> Path:
    return _state_dir(state_dir) / LEDGER_NAME


def _fresh_budget() -> dict[str, Any]:
    return {
        "truth_label": TRUTH,
        "stake_epoch": STAKE_EPOCH,
        "realized_pnl_stgm": 0.0,
        "realized_pnl_stgm_legacy_v2": 0.0,  # fenced ±0.0005 era
        "n_stakes": 0,
        "n_settled": 0,
        "n_wins": 0,
        "n_losses": 0,
        "open_staked_stgm": 0.0,
        "open_tickets": {},
        "settled_tickers": [],
        "halted": False,
        "halt_reason": "",
        "note": (
            "dollar-parity body STGM (0.001≡$1); win pays stake×(mult−1), "
            "loss costs stake; Kalshi USD off"
        ),
    }


def _load_budget(state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    path = _budget_path(state_dir)
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return _fresh_budget()
            # Accept V2 or V3; migrate soft fields without wiping history
            label = str(raw.get("truth_label") or "")
            if label in {TRUTH, TRUTH_LEGACY, "ALICE_15M_BODY_STGM_V2"}:
                raw.setdefault("open_tickets", {})
                raw.setdefault("settled_tickers", [])
                if raw.get("stake_epoch") != STAKE_EPOCH:
                    # Fence legacy PnL so epoch displays never mix economics
                    if "realized_pnl_stgm_legacy_v2" not in raw:
                        raw["realized_pnl_stgm_legacy_v2"] = float(
                            raw.get("realized_pnl_stgm") or 0.0
                        )
                        raw["realized_pnl_stgm"] = 0.0  # new epoch starts clean
                    raw["stake_epoch"] = STAKE_EPOCH
                    raw["truth_label"] = TRUTH
                    raw["epoch_note"] = (
                        "r1629 migrated: prior ±0.0005 PnL in "
                        "realized_pnl_stgm_legacy_v2; new rows use dollar-parity"
                    )
                return raw
        except Exception:
            pass
    return _fresh_budget()


def _save_budget(budget: dict[str, Any], state_dir: Optional[Path | str] = None) -> None:
    root = _state_dir(state_dir)
    root.mkdir(parents=True, exist_ok=True)
    payload = dict(budget)
    payload.update(
        {
            "truth_label": TRUTH,
            "stake_epoch": STAKE_EPOCH,
            "ts": time.time(),
            "stake_per_ticket": STGM_STAKE,
            "stgm_per_usd": STGM_PER_USD,
            "win_model": "stake*(net_mult-1)",
            "loss_model": "-stake",
            "win_reward_stgm": STGM_WIN_REWARD,
            "floor_total": STGM_FLOOR_TOTAL,
            "floor_m5": STGM_FLOOR_M5,
            "night_max_loss": STGM_NIGHT_MAX_LOSS,
            "max_open_stgm": STGM_MAX_OPEN,
        }
    )
    tmp = _budget_path(state_dir).with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(_budget_path(state_dir))


def _append_event(row: dict[str, Any], state_dir: Optional[Path | str] = None) -> None:
    from System.ledger_append import append_jsonl_line

    append_jsonl_line(_ledger_path(state_dir), row)


def _balances(state_dir: Optional[Path | str] = None) -> tuple[float, float]:
    """Return cached (whole-body spendable, ALICE_M5 pocket) balances."""
    try:
        cache = _state_dir(state_dir) / "stgm_economy_cache.json"
        data = json.loads(cache.read_text(encoding="utf-8"))
        total = float(data.get("spendable_total_stgm") or data.get("canonical_wallet_sum") or 0.0)
        balances = data.get("canonical_wallet_balances") or {}
        m5 = float(data.get("alice_m5_spendable_stgm") or balances.get(AGENT) or 0.0)
        return total, m5
    except Exception:
        return 0.0, 0.0


def can_stake_body_stgm(
    stake: float = STGM_STAKE,
    *,
    state_dir: Optional[Path | str] = None,
) -> tuple[bool, str]:
    stake = round(float(stake), 9)
    if stake <= 0.0 or stake > STGM_STAKE:
        return False, "invalid_or_oversize_stake"
    budget = _load_budget(state_dir)
    if budget.get("halted"):
        return False, str(budget.get("halt_reason") or "halted")
    pnl = float(budget.get("realized_pnl_stgm") or 0.0)
    if pnl - stake < -STGM_NIGHT_MAX_LOSS - 1e-12:
        budget["halted"] = True
        budget["halt_reason"] = f"night_max_loss_{STGM_NIGHT_MAX_LOSS}"
        _save_budget(budget, state_dir)
        return False, budget["halt_reason"]
    open_stgm = float(budget.get("open_staked_stgm") or 0.0)
    if open_stgm + stake > STGM_MAX_OPEN + 1e-12:
        return False, "max_open_stgm"
    total, m5 = _balances(state_dir)
    if total <= 0.0 or m5 <= 0.0:
        return False, "wallet_truth_unavailable"
    if total - stake < STGM_FLOOR_TOTAL:
        return False, f"floor_total_{STGM_FLOOR_TOTAL}"
    if m5 - stake < STGM_FLOOR_M5:
        return False, f"floor_m5_{STGM_FLOOR_M5}"
    return True, "ok"


def stake_body_stgm(
    *,
    ticker: str,
    asset: str,
    label: str,
    price: float,
    stake: float = STGM_STAKE,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Reserve one bounded real-STGM stake; the wallet mutates only at settle."""
    ticker = str(ticker or "").strip()
    if not ticker:
        return {"ok": False, "body_stgm": False, "reason": "missing_ticker", "stake": 0.0}
    budget = _load_budget(state_dir)
    if ticker in set(str(x) for x in budget.get("settled_tickers") or []):
        return {"ok": False, "body_stgm": False, "reason": "already_settled", "stake": 0.0}
    open_tickets = dict(budget.get("open_tickets") or {})
    if ticker in open_tickets:
        old = dict(open_tickets[ticker])
        return {"ok": True, "body_stgm": True, "duplicate": True, **old}
    ok, reason = can_stake_body_stgm(stake, state_dir=state_dir)
    if not ok:
        return {"ok": False, "body_stgm": False, "reason": reason, "stake": 0.0}

    amount = round(float(stake), 9)
    wager_id = "P15_" + hashlib.sha256(ticker.encode("utf-8")).hexdigest()[:16]
    ticket = {
        "wager_id": wager_id,
        "ticker": ticker,
        "asset": str(asset or ""),
        "label": str(label or ""),
        "price": round(float(price), 6),
        "stake": amount,
        "reserved_ts": time.time(),
        "token": "STGM",
    }
    open_tickets[ticker] = ticket
    budget["open_tickets"] = open_tickets
    budget["open_staked_stgm"] = round(
        float(budget.get("open_staked_stgm") or 0.0) + amount, 9
    )
    budget["n_stakes"] = int(budget.get("n_stakes") or 0) + 1
    _save_budget(budget, state_dir)
    _append_event({"kind": "stake_reserved", "truth_label": TRUTH, "policy": POLICY, **ticket}, state_dir)
    return {"ok": True, "body_stgm": True, **ticket}


def _repair_has_event(repair_log: Path, event_id: str) -> bool:
    if not repair_log.exists():
        return False
    needle = f'"event_id": "{event_id}"'
    needle_compact = f'"event_id":"{event_id}"'
    try:
        with repair_log.open("r", encoding="utf-8", errors="replace") as handle:
            return any(needle in line or needle_compact in line for line in handle)
    except OSError:
        return False


def _burn_loss(
    *,
    ticker: str,
    amount: float,
    repair_log: Path,
) -> dict[str, Any]:
    """Append one signed, attributed canonical STGM_SPEND for a loss."""
    event_id = "PRED15M_LOSS_" + hashlib.sha256(ticker.encode("utf-8")).hexdigest()[:20]
    if _repair_has_event(repair_log, event_id):
        return {"spent_stgm": 0.0, "duplicate": True, "event_id": event_id}

    from Kernel.inference_economy import _get_serial, sign_block
    from System.ledger_append import append_ledger_line
    from System.stgm_economy import make_economic_attribution_key

    now = time.time()
    amount = round(float(amount), 9)
    signing_node = _get_serial()
    target = "PREDICTION_LEARNING_LOSS"
    trace_id = f"prediction15m:{ticker}:loss"
    signature_body = f"{signing_node}:{target}:{amount}:{now}"
    row = {
        "tx_type": "STGM_SPEND",
        "event": "PREDICTION_LEARNING_LOSS",
        "event_kind": "PREDICTION_LEARNING_STGM_SETTLE",
        "event_id": event_id,
        "agent_id": AGENT,
        "amount": amount,
        "timestamp": now,
        "ts": now,
        "target_node": target,
        "ticker": ticker,
        "organ_id": ORGAN,
        "trace_id": trace_id,
        "source_ledger": SOURCE,
        "tick_id": ticker,
        "policy": POLICY,
        "reason": "settled_prediction_loss_real_stgm",
        "signing_node": signing_node,
        "ed25519_sig": sign_block(signature_body),
    }
    row["economic_attribution_key"] = make_economic_attribution_key(
        organ_id=ORGAN,
        trace_id=trace_id,
        source_ledger=SOURCE,
        tick_id=ticker,
    )
    append_ledger_line(repair_log, row)
    return {"spent_stgm": amount, "event_id": event_id, "signed": True}


def _reward_win(ticker: str, amount_stgm: float) -> dict[str, Any]:
    from System.swarm_atp_synthase import mint_receipted_work_pulse

    return mint_receipted_work_pulse(
        "verified_execution",
        f"prediction15m:{ticker}:verified_win",
        beneficiary=AGENT,
        amount_stgm=round(float(amount_stgm), 9),
    )


def settle_body_stgm(
    *,
    ticker: str,
    asset: str,
    label: str,
    price: float,
    win: bool,
    stake: float = STGM_STAKE,
    state_dir: Optional[Path | str] = None,
    repair_log: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Settle a reserved ticket exactly once against canonical body STGM.

    r1629 dollar-parity: win pays stake×(net_mult−1), loss costs full stake.
    """
    ticker = str(ticker or "").strip()
    budget = _load_budget(state_dir)
    settled = set(str(x) for x in budget.get("settled_tickers") or [])
    if ticker in settled:
        return {"ok": True, "duplicate": True, "ticker": ticker, "pnl_stgm": 0.0}
    open_tickets = dict(budget.get("open_tickets") or {})
    ticket = dict(open_tickets.get(ticker) or {})
    if not ticker or not ticket:
        return {"ok": False, "reason": "no_reserved_stake", "ticker": ticker}
    amount = round(float(ticket.get("stake") or stake), 9)
    # Cap oversized legacy tickets at new stake ceiling
    if amount > STGM_STAKE * 1.01:
        amount = STGM_STAKE
    px = float(ticket.get("price") or price or 0.5)
    target_log = Path(repair_log) if repair_log is not None else REPAIR_LOG
    mult = net_multiplier(px)
    # Target economic PnL (mirrors $ at 0.001 STGM ≡ $1)
    target_pnl = stgm_pnl_from_price(px, win=bool(win), stake_stgm=amount)

    try:
        if win:
            # Mint the win reward equal to target profit (asymmetric, not flat stake)
            win_amt = max(0.0, float(target_pnl))
            effect = _reward_win(ticker, win_amt)
            actual = round(float(effect.get("minted_stgm") or 0.0), 9)
            kind = "win"
            pnl = actual if actual > 0 else win_amt  # book target if mint soft-fails
            if actual <= 0 and win_amt > 0:
                pnl = win_amt  # accounting still tracks parity even if mint skipped
                effect = {**effect, "accounting_pnl": win_amt}
        else:
            loss_amt = abs(float(target_pnl))  # == amount for dollar-parity
            if float(budget.get("realized_pnl_stgm") or 0.0) - loss_amt < -STGM_NIGHT_MAX_LOSS - 1e-12:
                budget["halted"] = True
                budget["halt_reason"] = f"night_max_loss_{STGM_NIGHT_MAX_LOSS}"
                effect = {"spent_stgm": 0.0, "refused": budget["halt_reason"]}
                actual = 0.0
                pnl = 0.0
            else:
                effect = _burn_loss(ticker=ticker, amount=loss_amt, repair_log=target_log)
                actual = round(float(effect.get("spent_stgm") or 0.0), 9)
                pnl = -actual if actual > 0 else -loss_amt
            kind = "loss"
    except Exception as exc:
        effect = {"refused": f"{type(exc).__name__}:{exc}"}
        actual = 0.0
        pnl = float(target_pnl)  # still record economic intent
        kind = "win" if win else "loss"

    open_tickets.pop(ticker, None)
    settled.add(ticker)
    budget["open_tickets"] = open_tickets
    budget["settled_tickers"] = sorted(settled)[-4096:]
    budget["open_staked_stgm"] = max(
        0.0, round(float(budget.get("open_staked_stgm") or 0.0) - amount, 9)
    )
    budget["n_settled"] = int(budget.get("n_settled") or 0) + 1
    budget["n_wins"] = int(budget.get("n_wins") or 0) + (1 if win else 0)
    budget["n_losses"] = int(budget.get("n_losses") or 0) + (0 if win else 1)
    budget["realized_pnl_stgm"] = round(
        float(budget.get("realized_pnl_stgm") or 0.0) + pnl, 9
    )
    if float(budget["realized_pnl_stgm"]) <= -STGM_NIGHT_MAX_LOSS:
        budget["halted"] = True
        budget["halt_reason"] = f"night_max_loss_{STGM_NIGHT_MAX_LOSS}"
    _save_budget(budget, state_dir)
    row = {
        "kind": kind,
        "truth_label": TRUTH,
        "policy": POLICY,
        "stake_epoch": STAKE_EPOCH,
        "ts": time.time(),
        "ticker": ticker,
        "asset": str(asset or ""),
        "label": str(label or ""),
        "price": round(float(px), 6),
        "stake": amount,
        "mult_net": mult,
        "win": bool(win),
        "pnl_stgm": pnl,
        "pnl_usd_hyp": round(pnl / STGM_PER_USD, 4) if STGM_PER_USD else 0.0,
        "effect": effect,
    }
    _append_event(row, state_dir)
    return {"ok": True, "body_stgm": True, **row}


def status_snapshot(state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    total, m5 = _balances(state_dir)
    return {
        "truth_label": TRUTH,
        "token": "STGM",
        "stake_per_ticket": STGM_STAKE,
        "win_reward_stgm": STGM_WIN_REWARD,
        "spendable_total_stgm": total,
        "alice_m5_stgm": m5,
        "budget": _load_budget(state_dir),
        "safety": {
            "kalshi_usd": "OFF",
            "settlement": "signed loss burn / signed verified-win work pulse",
            "floor_total": STGM_FLOOR_TOTAL,
            "floor_m5": STGM_FLOOR_M5,
            "night_max_loss": STGM_NIGHT_MAX_LOSS,
            "max_open_stgm": STGM_MAX_OPEN,
        },
    }


def reconcile_reservations(
    active_tickers: set[str] | list[str] | tuple[str, ...],
    *,
    state_dir: Optional[Path | str] = None,
    now: Optional[float] = None,
    stale_after_s: float = 30 * 60,
) -> dict[str, Any]:
    """Release settled or abandoned reservations without touching the wallet.

    A reservation is only an exposure marker; canonical STGM moves at settle.
    This repairs stale markers left by a writer handoff or crash. A ticker is
    released when its V2 settlement is already in the body ledger, or when it
    disappeared from the paper open book for longer than ``stale_after_s``.
    """
    current = float(time.time() if now is None else now)
    active = {str(x) for x in active_tickers if str(x)}
    budget = _load_budget(state_dir)
    tickets = dict(budget.get("open_tickets") or {})
    settled_body: set[str] = set()
    path = _ledger_path(state_dir)
    if path.exists():
        try:
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                if row.get("truth_label") != TRUTH or row.get("kind") not in {"win", "loss"}:
                    continue
                ticker = str(row.get("ticker") or "")
                if ticker:
                    settled_body.add(ticker)
        except OSError:
            pass

    released: list[dict[str, Any]] = []
    kept: dict[str, Any] = {}
    for ticker, ticket in tickets.items():
        age = max(0.0, current - float((ticket or {}).get("reserved_ts") or current))
        reason = ""
        if ticker in settled_body:
            reason = "settlement_already_receipted"
        elif ticker not in active and age >= max(1.0, float(stale_after_s)):
            reason = "missing_from_open_book_stale"
        if reason:
            released.append(
                {
                    "kind": "reservation_reconciled",
                    "truth_label": TRUTH,
                    "policy": POLICY,
                    "ts": current,
                    "ticker": ticker,
                    "stake": float((ticket or {}).get("stake") or 0.0),
                    "age_s": round(age, 3),
                    "reason": reason,
                    "wallet_mutation": False,
                }
            )
        else:
            kept[ticker] = ticket
    if released:
        budget["open_tickets"] = kept
        budget["open_staked_stgm"] = round(
            sum(float((ticket or {}).get("stake") or 0.0) for ticket in kept.values()), 9
        )
        budget["last_reconcile_ts"] = current
        budget["last_reconcile_released"] = len(released)
        _save_budget(budget, state_dir)
        for row in released:
            _append_event(row, state_dir)
    return {
        "ok": True,
        "released": len(released),
        "released_tickers": [row["ticker"] for row in released],
        "open_staked_stgm": float(budget.get("open_staked_stgm") or 0.0),
        "wallet_mutation": False,
    }


__all__ = [
    "STGM_STAKE",
    "STGM_WIN_REWARD",
    "can_stake_body_stgm",
    "stake_body_stgm",
    "settle_body_stgm",
    "reconcile_reservations",
    "status_snapshot",
]
