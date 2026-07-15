#!/usr/bin/env python3
"""Ledger deal — George YES 2026-07-13 (r1648) + owner dual-every-round (r1649).

  • 3 hands max · max 2 same direction
  • $1 flat tickets (1 contract ≈ entry $)
  • DUAL LANE: every paper/STGM ticket in 70–88¢ also places US $ (owner order)
  • Rainman SIT still skips dollars; FIRE/THIN mirror
  • Night stop −$5 · budget $10
  • Every real fill receipted; live EV vs paper unit

Single source of truth for caps.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".sifta_state"
DEAL_FILE = "ledger_deal.json"
EV_LOG = "kalshi_usd_ev_log.jsonl"
TRUTH = "LEDGER_DEAL_V1"

# r1702 owner: TWO concurrent bags · $2 AMMO each (2 contracts/ticket).
# max 2 same direction still (both YES or both NO ok; no third stack).
# r1709 owner: recover cash — prefer ONE bag (was 2); fewer double-death windows
MAX_OPEN = 1
MAX_SAME_DIR = 1
TARGET_CONCURRENT_OPEN = 1
# r1693 owner: AMMO default $2 each = 2 contracts per ticket (was 1)
STAKE_USD = 2.0
AMMO_FILE = "kalshi_usd_ammo.json"
AMMO_DEFAULT = 2.0
AMMO_MIN = 1.0
AMMO_MAX = 5.0  # hard cap — cherish stash
# r1649: match paper shelf so STGM ticket ⇒ US $ (owner: every round automatically)
# r1691: field winners rarely stay under 55¢ — allow ≤65¢, prefer cheaper
USD_MIN_ENTRY = 0.40
USD_MAX_ENTRY = 0.65
PAPER_MIN_ENTRY = 0.40
PAPER_MAX_ENTRY = 0.65
MAX_NIGHT_LOSS_USD = 5.0
MAX_BUDGET_USD = 12.0  # room for 2 × ~$1.3 premium at 2 contracts
# False = FIRE + THIN place dollars; only rainman SIT skips US $
FIRE_ONLY_USD = False
MIN_VOLUME = 0.0  # owner dual: don't dust-veto her paper tickets
STAKE_RAISE_REQUIRES_EVIDENCE = True
DUAL_EVERY_PAPER_BET = True


def _state_root(state_dir: Optional[Path | str] = None) -> Path:
    root = Path(state_dir) if state_dir else STATE
    if root.name != ".sifta_state":
        root = root / ".sifta_state"
    return root


def get_ammo_usd(*, state_dir: Optional[Path | str] = None) -> float:
    """Owner AMMO — dollars-per-ticket face (1 AMMO ≈ 1 Kalshi contract unit)."""
    root = _state_root(state_dir)
    p = root / AMMO_FILE
    if p.exists():
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            v = float(d.get("ammo_usd") if d.get("ammo_usd") is not None else d.get("ammo") or STAKE_USD)
            return max(AMMO_MIN, min(AMMO_MAX, v))
        except Exception:
            pass
    return float(STAKE_USD)


def set_ammo_usd(
    ammo: float,
    *,
    state_dir: Optional[Path | str] = None,
    reason: str = "",
) -> dict[str, Any]:
    """Persist AMMO from glass text box (default $2 each)."""
    root = _state_root(state_dir)
    root.mkdir(parents=True, exist_ok=True)
    try:
        v = float(ammo)
    except (TypeError, ValueError):
        v = AMMO_DEFAULT
    v = max(AMMO_MIN, min(AMMO_MAX, v))
    row = {
        "ammo_usd": v,
        "contracts_per_ticket": int(round(v)),
        "ts": time.time(),
        "reason": str(reason or "")[:200],
        "truth_label": TRUTH,
        "receipt_id": "r1693-ammo-2-default",
        "note": "AMMO = contracts per dual ticket (Kalshi $1 face each)",
    }
    (root / AMMO_FILE).write_text(json.dumps(row, indent=2, sort_keys=True), encoding="utf-8")
    return row


def contracts_for_ammo(
    *,
    ammo_usd: Optional[float] = None,
    state_dir: Optional[Path | str] = None,
) -> int:
    """Integer contract count from AMMO (min 1, max 5)."""
    a = float(ammo_usd) if ammo_usd is not None else get_ammo_usd(state_dir=state_dir)
    return max(1, min(int(AMMO_MAX), int(round(a))))


def caps_dict(*, state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    ammo = get_ammo_usd(state_dir=state_dir)
    return {
        "truth_label": TRUTH,
        "max_open": MAX_OPEN,
        "max_same_dir": MAX_SAME_DIR,
        "target_concurrent_open": TARGET_CONCURRENT_OPEN,
        "stake_usd": ammo,
        "ammo_usd": ammo,
        "contracts_per_ticket": contracts_for_ammo(ammo_usd=ammo, state_dir=state_dir),
        "usd_band": [USD_MIN_ENTRY, USD_MAX_ENTRY],
        "paper_band": [PAPER_MIN_ENTRY, PAPER_MAX_ENTRY],
        "max_night_loss_usd": MAX_NIGHT_LOSS_USD,
        "max_budget_usd": MAX_BUDGET_USD,
        "fire_only_usd": FIRE_ONLY_USD,
        "dual_every_paper_bet": DUAL_EVERY_PAPER_BET,
        "min_volume": MIN_VOLUME,
        "stake_raise_requires_evidence": STAKE_RAISE_REQUIRES_EVIDENCE,
        "note": (
            "r1706: TWO bags · AMMO $2 · STGM=US$ scalp copy · fee-true TP · "
            "force flat ≤7:30 · band 40-65¢ · shadow training extra only."
        ),
    }


def persist_deal(*, state_dir: Optional[Path | str] = None) -> Path:
    root = _state_root(state_dir)
    root.mkdir(parents=True, exist_ok=True)
    # ensure ammo file exists at default $2
    if not (root / AMMO_FILE).exists():
        set_ammo_usd(AMMO_DEFAULT, state_dir=root, reason="persist_deal_default")
    p = root / DEAL_FILE
    row = {
        **caps_dict(state_dir=root),
        "ts": time.time(),
        "owner_yes": True,
        "owner_phrase": "TWO concurrent · AMMO $2 each · dual STGM+US$",
        "receipt_id": "r1702-two-bags-ammo-2",
    }
    p.write_text(json.dumps(row, indent=2, sort_keys=True), encoding="utf-8")
    return p


def log_ev_row(row: dict[str, Any], *, state_dir: Optional[Path | str] = None) -> None:
    """Append one real-fill / settle comparison row (paper unit vs live)."""
    root = Path(state_dir) if state_dir else STATE
    if root.name != ".sifta_state":
        root = root / ".sifta_state"
    root.mkdir(parents=True, exist_ok=True)
    out = dict(row)
    out.setdefault("ts", time.time())
    out.setdefault("truth_label", "KALSHI_USD_EV_LOG_V1")
    out.setdefault("deal", TRUTH)
    try:
        with (root / EV_LOG).open("a", encoding="utf-8") as f:
            f.write(json.dumps(out, ensure_ascii=False, sort_keys=True) + "\n")
    except OSError:
        pass


def maybe_write_periodic_audit(
    *,
    state_dir: Path | str = STATE,
    now: Optional[float] = None,
) -> dict[str, Any]:
    """Forward to the USD auditor without a module-import cycle.

    ``kalshi_usd_audit`` imports the frozen deal constants above, so the import
    belongs inside this function after ``ledger_deal`` has initialized.
    """
    from System.kalshi_usd_audit import maybe_write_periodic_audit as _write

    return _write(state_dir=state_dir, now=now)


def paper_unit_pnl(win: bool, price: float) -> float:
    """Honest $1 unit at price p."""
    p = max(0.01, min(0.99, float(price)))
    if win:
        return round(1.0 / p - 1.0, 4)
    return -1.0


def live_contract_pnl(win: bool, price: float) -> float:
    """1 contract bought at price p: win +(1-p), lose -p."""
    p = max(0.01, min(0.99, float(price)))
    if win:
        return round(1.0 - p, 4)
    return round(-p, 4)


__all__ = [
    "MAX_OPEN",
    "MAX_SAME_DIR",
    "TARGET_CONCURRENT_OPEN",
    "STAKE_USD",
    "AMMO_DEFAULT",
    "AMMO_FILE",
    "USD_MIN_ENTRY",
    "USD_MAX_ENTRY",
    "PAPER_MIN_ENTRY",
    "PAPER_MAX_ENTRY",
    "MAX_NIGHT_LOSS_USD",
    "MAX_BUDGET_USD",
    "FIRE_ONLY_USD",
    "MIN_VOLUME",
    "caps_dict",
    "persist_deal",
    "get_ammo_usd",
    "set_ammo_usd",
    "contracts_for_ammo",
    "log_ev_row",
    "maybe_write_periodic_audit",
    "paper_unit_pnl",
    "live_contract_pnl",
    "TRUTH",
]
