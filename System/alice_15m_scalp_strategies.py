#!/usr/bin/env python3
"""r1684-d — Frozen scalp strategy arms for STGM laboratory.

All arms see identical point-in-time tape. Each may produce 0–3 round trips
per ticker/window. No forced trade quota. No averaging down. No martingale.

Truth: ALICE_15M_SCALP_STRATEGIES_V1
Receipt: r1684-d-scalp-strategy-tournament (strategy freeze)
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol

from System.alice_15m_execution_sim import clamp_price, parse_levels
from System.alice_15m_scalp_learner import estimate_taker_fee, evaluate_scalp

TRUTH = "ALICE_15M_SCALP_STRATEGIES_V1"
STRATEGY_VERSION = "v1.0.3-r1712-salvage-exit"
RECEIPT = "r1684-d-scalp-strategy-tournament"
REGIME_RECEIPT = "r20260714-updown-regime-align"
SALVAGE_RECEIPT = "r20260714-salvage-exit-red-field"

MAJORS = frozenset({"BTC", "ETH", "SOL", "XRP", "BNB"})
WEIRD = frozenset({"HYPE", "ZEC", "NEAR"})
MAX_RT_PER_TICKER_WINDOW = 3
MAX_OPEN_POS = 3
MIN_EDGE = 0.03  # take profits fee-true
MIN_HOLD_MS = 25_000  # r1686: bank greens faster
NO_ENTRY_SECS = 45.0  # r1685: only block new entries in last 45s
FLATTEN_SECS = 45.0
# r1685: scalping starts minute-14 / open bell — not m7/m11
SCALP_ENTRY_SECS_MAX = 15 * 60
# r1686: buy low sell high
SCALP_MIN_ENTRY = 0.40
SCALP_MAX_ENTRY = 0.65  # r1691: under 55 too tight for field winners
MIN_SPREAD = 0.005
MAX_SPREAD = 0.06
MIN_DEPTH = 0.5
MIN_VOLUME_24H = 500.0

# r1711 WCT r20260714-updown-regime-align — config (not buried magic)
# No fade when the live implied side is this strong and the field agrees.
REGIME_GATE_ENABLED = True
REGIME_GATE_IMPLIED_THRESH = 0.70
REGIME_GATE_FIELD_BREADTH_MIN = 0.20  # |majors_breadth| agreement floor

# r1712 WCT r20260714-salvage-exit-red-field — cut dead tickets, keep residual
# Side implied ≤ thresh with enough clock left → exit at quoted bid (not ride to 0).
SALVAGE_EXIT_ENABLED = True
SALVAGE_SIDE_IMPLIED_MAX = 0.30  # config threshold (acceptance: fire ≤0.30, no-fire @0.45)
SALVAGE_MIN_SECS_LEFT = 90.0  # need >90s left (not endgame force-flat zone)
SALVAGE_EXIT_REASON = "salvage_exit_red_field"
SALVAGE_COHORT = "salvage_exit_red_field"  # own WHY cohort for honest learner stats

# r1713 soft adverse mid-tail (shared STGM + US$ — one definition, both lanes)
SOFT_ADVERSE_ENABLED = True
SOFT_ADVERSE_SIDE_IMPLIED_MAX = 0.42
SOFT_ADVERSE_MAX_SECS_LEFT = 180.0  # only when <180s left
SOFT_ADVERSE_MAX_LOSS_PER_CONTRACT = 0.15  # bid not worse than entry−15¢
SOFT_ADVERSE_REASON = "soft_adverse_red_field"

# r1714 spray correlation — max same-side tickets per 15m window (both lanes)
MAX_SAME_SIDE_PER_WINDOW = 2
SPRAY_CORRELATION_REASON = "spray_correlation_cap"


@dataclass
class Intent:
    """Strategy decision — submit / hold / exit / no_trade."""

    action: str  # enter | exit | hold | no_trade | flatten
    side: str = "yes"
    order_action: str = "buy"  # buy | sell
    price: float = 0.5
    quantity: float = 1.0
    tif: str = "ioc"
    post_only: bool = False
    reduce_only: bool = False
    reason: str = ""
    strategy_id: str = ""
    confidence: float = 0.0


@dataclass
class ArmState:
    strategy_id: str
    window_id: str = ""
    ticker: str = ""
    open_side: str = ""
    open_qty: float = 0.0
    open_entry: float = 0.0
    open_ts_ms: int = 0
    n_round_trips: int = 0
    cooldown_until_ms: int = 0
    trail_best: float = 0.0
    features_hash: str = ""
    no_trade_reasons: list[str] = field(default_factory=list)
    # r1709 P0.8: at most one resting entry/exit order per ticker
    open_order_id: str = ""
    open_order_price: float = 0.0
    open_order_qty: float = 0.0
    open_order_action: str = ""  # buy|sell
    queue_state: str = ""  # resting|filled|canceled|unknown


class Strategy(Protocol):
    strategy_id: str
    version: str

    def decide(
        self,
        book: dict[str, Any],
        *,
        state: ArmState,
        field: Optional[dict[str, Any]] = None,
    ) -> Intent: ...


def _bbo(book: dict[str, Any]) -> dict[str, Optional[float]]:
    yes_bids = parse_levels(book.get("yes_bids"))
    yes_asks = parse_levels(book.get("yes_asks"))
    no_bids = parse_levels(book.get("no_bids"))
    yb = yes_bids[0][0] if yes_bids else None
    ya = yes_asks[0][0] if yes_asks else None
    if ya is None and no_bids:
        ya = clamp_price(1.0 - no_bids[0][0])
    mid = book.get("yes_mid")
    if mid is None and yb is not None and ya is not None:
        mid = (yb + ya) / 2.0
    elif mid is None and yb is not None:
        mid = yb
    elif mid is not None:
        mid = float(mid)
    spread = (ya - yb) if (ya is not None and yb is not None) else None
    bid_sz = yes_bids[0][1] if yes_bids else 0.0
    ask_sz = yes_asks[0][1] if yes_asks else (no_bids[0][1] if no_bids else 0.0)
    return {
        "yes_bid": yb,
        "yes_ask": ya,
        "yes_mid": float(mid) if mid is not None else None,
        "spread": spread,
        "bid_sz": float(bid_sz),
        "ask_sz": float(ask_sz),
    }


def _secs(book: dict[str, Any]) -> Optional[float]:
    s = book.get("seconds_left")
    try:
        return float(s) if s is not None else None
    except (TypeError, ValueError):
        return None


def _asset(book: dict[str, Any]) -> str:
    return str(book.get("asset") or "").upper()


def regime_gate(
    *,
    side: str,
    yes_mid: Optional[float],
    field: Optional[dict[str, Any]] = None,
    implied_thresh: Optional[float] = None,
    enabled: Optional[bool] = None,
) -> Optional[str]:
    """Block fading a strong live odds regime (r20260714-updown-regime-align).

    When UP implied (yes_mid) >= thresh and co-dir field agrees UP → no DOWN.
    Symmetric: DOWN implied (1-yes) >= thresh and field agrees DOWN → no YES.

    Skipping the window/ticket is a valid win. Returns reject reason or None.
    Threshold lives in REGIME_GATE_IMPLIED_THRESH (config), not buried magic.
    """
    if enabled is None:
        enabled = bool(REGIME_GATE_ENABLED)
    if not enabled:
        return None
    thresh = float(
        REGIME_GATE_IMPLIED_THRESH if implied_thresh is None else implied_thresh
    )
    side_l = "yes" if str(side).lower() in ("yes", "up") else "no"
    try:
        ym = float(yes_mid) if yes_mid is not None else None
    except (TypeError, ValueError):
        ym = None
    if ym is None:
        return None  # no mid → other gates handle
    ym = max(0.0, min(1.0, ym))
    up_imp = ym
    down_imp = 1.0 - ym

    f = field or {}
    # field agreement: breadth, anchor_side, or market alone when field incomplete
    breadth = f.get("majors_breadth")
    anchor = str(f.get("anchor_side") or f.get("field_anchor") or "").lower()
    field_up = False
    field_down = False
    field_known = False
    try:
        if breadth is not None:
            b = float(breadth)
            field_known = True
            if b >= float(REGIME_GATE_FIELD_BREADTH_MIN):
                field_up = True
            elif b <= -float(REGIME_GATE_FIELD_BREADTH_MIN):
                field_down = True
    except (TypeError, ValueError):
        pass
    if anchor in ("yes", "up"):
        field_known = True
        field_up = True
    elif anchor in ("no", "down"):
        field_known = True
        field_down = True
    # When field silent: strong ticket odds alone define regime (16:47 wound)
    if not field_known:
        if up_imp >= thresh:
            field_up = True
        if down_imp >= thresh:
            field_down = True

    if side_l == "no" and up_imp >= thresh - 1e-12 and field_up:
        return "regime_block_down_vs_up_drift"
    if side_l == "yes" and down_imp >= thresh - 1e-12 and field_down:
        return "regime_block_up_vs_down_drift"
    return None


def regime_preferred_side(
    yes_mid: Optional[float],
    *,
    field: Optional[dict[str, Any]] = None,
    implied_thresh: Optional[float] = None,
) -> Optional[str]:
    """Side the regime wants, or None if no strong regime."""
    try:
        ym = float(yes_mid) if yes_mid is not None else None
    except (TypeError, ValueError):
        return None
    if ym is None:
        return None
    thresh = float(
        REGIME_GATE_IMPLIED_THRESH if implied_thresh is None else implied_thresh
    )
    # probe both sides — whichever is not blocked by a strong opposite regime
    if regime_gate(side="no", yes_mid=ym, field=field, implied_thresh=thresh) is not None:
        return "yes"  # DOWN blocked → prefer UP
    if regime_gate(side="yes", yes_mid=ym, field=field, implied_thresh=thresh) is not None:
        return "no"
    return None


def shared_entry_gates(
    book: dict[str, Any],
    state: ArmState,
    *,
    allow_weird: bool = False,
    field: Optional[dict[str, Any]] = None,
    proposed_side: Optional[str] = None,
) -> Optional[str]:
    """Return reject reason or None if entry allowed."""
    asset = _asset(book)
    if asset in WEIRD and not allow_weird:
        return "weird_asset"
    if asset and asset not in MAJORS and asset not in WEIRD:
        # DOGE etc — allow majors path only unless in MAJORS
        if asset not in MAJORS:
            return "not_liquid_major"
    if state.n_round_trips >= MAX_RT_PER_TICKER_WINDOW:
        return "max_round_trips"
    if state.open_qty > 1e-12:
        return "already_open"
    recv = int(book.get("recv_ts_ms") or 0)
    if recv and state.cooldown_until_ms and recv < state.cooldown_until_ms:
        return "cooldown"
    secs = _secs(book)
    if secs is not None and secs < NO_ENTRY_SECS:
        return "too_late_to_enter"
    # r1685: minute-7/11 does NOT apply to scalping — allow from open / m14
    if secs is not None and secs > SCALP_ENTRY_SECS_MAX:
        return "too_early_open_band"
    bbo = _bbo(book)
    if bbo["yes_mid"] is None:
        return "no_mid"
    spread = bbo["spread"]
    if spread is None:
        return "no_spread"
    if spread > MAX_SPREAD:
        return "spread_too_wide"
    if spread < 0:
        return "crossed_book"
    depth = min(float(bbo["bid_sz"] or 0), float(bbo["ask_sz"] or 0))
    if depth < MIN_DEPTH:
        return "thin_depth"
    vol = float(book.get("volume_24h") or 0)
    if vol < MIN_VOLUME_24H:
        return "low_volume"
    # buy-low gate on cheaper side of book
    mid = bbo["yes_mid"]
    if mid is not None:
        cheap = min(float(mid), 1.0 - float(mid))
        if cheap > SCALP_MAX_ENTRY:
            return "too_expensive_both_sides"
        if cheap < SCALP_MIN_ENTRY - 0.05:
            return "too_cheap_lottery"
    # r1711: regime gate when caller already knows proposed side
    if proposed_side:
        rg = regime_gate(side=proposed_side, yes_mid=mid, field=field)
        if rg:
            return rg
    return None


def side_implied_prob(side: str, yes_mid: float) -> float:
    """Market-implied probability of our held side winning (0–1)."""
    ym = max(0.0, min(1.0, float(yes_mid)))
    side_l = "yes" if str(side).lower() in ("yes", "up") else "no"
    return ym if side_l == "yes" else (1.0 - ym)


def salvage_exit_should_fire(
    *,
    side: str,
    yes_mid: Optional[float],
    secs_left: Optional[float],
    side_implied_max: Optional[float] = None,
    min_secs_left: Optional[float] = None,
    enabled: Optional[bool] = None,
) -> bool:
    """True when held side is dead vs field and we still have clock to salvage residual."""
    if enabled is None:
        enabled = bool(SALVAGE_EXIT_ENABLED)
    if not enabled:
        return False
    if yes_mid is None or secs_left is None:
        return False
    try:
        secs = float(secs_left)
        ym = float(yes_mid)
    except (TypeError, ValueError):
        return False
    thresh = float(
        SALVAGE_SIDE_IMPLIED_MAX if side_implied_max is None else side_implied_max
    )
    min_secs = float(SALVAGE_MIN_SECS_LEFT if min_secs_left is None else min_secs_left)
    # need more than min_secs left (strict >)
    if secs <= min_secs + 1e-9:
        return False
    imp = side_implied_prob(side, ym)
    return imp <= thresh + 1e-12


def salvage_exit_intent(
    book: dict[str, Any],
    state: ArmState,
    *,
    exit_px: Optional[float] = None,
) -> Optional[Intent]:
    """Build salvage exit at quoted side bid when red-field rule fires."""
    if state.open_qty <= 1e-12:
        return None
    secs = _secs(book)
    bbo = _bbo(book)
    mid = bbo["yes_mid"]
    side = state.open_side or "yes"
    if not salvage_exit_should_fire(side=side, yes_mid=mid, secs_left=secs):
        return None
    # exit at actually-quoted bid of held side
    px_map = side_executable_prices(book)
    if exit_px is not None:
        px = clamp_price(float(exit_px))
    elif side == "yes" and px_map["bid_yes"] is not None:
        px = clamp_price(float(px_map["bid_yes"]))
    elif side == "no" and px_map["bid_no"] is not None:
        px = clamp_price(float(px_map["bid_no"]))
    else:
        # fallback aggressive
        px = 0.01
    imp = side_implied_prob(side, float(mid or 0.5))
    return Intent(
        action="exit",
        side=side,
        order_action="sell",
        price=px,
        quantity=state.open_qty,
        reduce_only=True,
        reason=SALVAGE_EXIT_REASON,
        strategy_id=state.strategy_id,
        confidence=float(imp),
    )


def soft_adverse_should_fire(
    *,
    side: str,
    yes_mid: Optional[float],
    secs_left: Optional[float],
    entry: Optional[float] = None,
    exit_bid: Optional[float] = None,
    side_implied_max: Optional[float] = None,
    max_secs_left: Optional[float] = None,
    max_loss: Optional[float] = None,
    enabled: Optional[bool] = None,
) -> bool:
    """Mid-tail cut: side weak, clock short, residual still salvageable at bid.

    Config: side_imp ≤ 0.42, secs < 180, bid ≥ entry − 15¢ (per contract).
    Shared by STGM paper and US$ take-profit — never fork a USD-only rule.
    """
    if enabled is None:
        enabled = bool(SOFT_ADVERSE_ENABLED)
    if not enabled:
        return False
    if yes_mid is None or secs_left is None:
        return False
    try:
        secs = float(secs_left)
        ym = float(yes_mid)
    except (TypeError, ValueError):
        return False
    thr = float(
        SOFT_ADVERSE_SIDE_IMPLIED_MAX
        if side_implied_max is None
        else side_implied_max
    )
    max_s = float(
        SOFT_ADVERSE_MAX_SECS_LEFT if max_secs_left is None else max_secs_left
    )
    loss_cap = float(
        SOFT_ADVERSE_MAX_LOSS_PER_CONTRACT if max_loss is None else max_loss
    )
    # only when less than max_s left (late mid-window), not force-flat yet
    if secs >= max_s - 1e-9:
        return False
    if secs <= 90.0:  # salvage / force-flat zones own deeper clock
        return False
    imp = side_implied_prob(side, ym)
    if imp > thr + 1e-12:
        return False
    if entry is not None and exit_bid is not None:
        try:
            if float(exit_bid) < float(entry) - loss_cap - 1e-12:
                return False  # already past soft cap → leave to salvage/force-flat
        except (TypeError, ValueError):
            pass
    return True


def _exit_if_open(
    book: dict[str, Any],
    state: ArmState,
    *,
    min_edge: float = MIN_EDGE,
    trail_giveback: float = 0.02,
    time_stop: bool = True,
) -> Optional[Intent]:
    if state.open_qty <= 1e-12:
        return None
    secs = _secs(book)
    bbo = _bbo(book)
    mid = bbo["yes_mid"]
    if mid is None:
        return Intent(action="hold", reason="open_no_mark")
    side = state.open_side or "yes"
    ev = evaluate_scalp(
        side=side,
        entry_price=state.open_entry,
        yes_mid=mid,
        contracts=state.open_qty,
        yes_bid=bbo["yes_bid"],
        yes_ask=bbo["yes_ask"],
        min_edge=min_edge,
    )
    # track trail on side mark
    mark = float(ev["exit_px"])
    if mark > state.trail_best:
        state.trail_best = mark
    recv = int(book.get("recv_ts_ms") or 0)
    age_ms = recv - state.open_ts_ms if recv and state.open_ts_ms else 0

    # r1712: salvage residual when side is dead vs field (before green-only hold)
    salv = salvage_exit_intent(book, state, exit_px=float(ev["exit_px"]))
    if salv is not None:
        return salv
    # r1713: soft adverse mid-tail (shared stack)
    if soft_adverse_should_fire(
        side=side,
        yes_mid=mid,
        secs_left=secs,
        entry=state.open_entry,
        exit_bid=float(ev["exit_px"]),
    ):
        return Intent(
            action="exit",
            side=side,
            order_action="sell",
            price=clamp_price(float(ev["exit_px"])),
            quantity=state.open_qty,
            reduce_only=True,
            reason=SOFT_ADVERSE_REASON,
            strategy_id=state.strategy_id,
            confidence=side_implied_prob(side, float(mid)),
        )

    if secs is not None and secs <= FLATTEN_SECS:
        return Intent(
            action="flatten",
            side=side,
            order_action="sell",
            price=0.01,
            quantity=state.open_qty,
            reduce_only=True,
            reason="time_flatten_cutoff",
            strategy_id=state.strategy_id,
        )
    if age_ms >= MIN_HOLD_MS and ev.get("scalp_ok"):
        return Intent(
            action="exit",
            side=side,
            order_action="sell",
            price=0.01 if side == "yes" else 0.01,
            quantity=state.open_qty,
            reduce_only=True,
            reason="fee_true_take_profit",
            strategy_id=state.strategy_id,
            confidence=float(ev.get("net_usd") or 0),
        )
    # trailing reversal: give back trail_giveback from best
    if age_ms >= MIN_HOLD_MS and state.trail_best > 0 and mark <= state.trail_best - trail_giveback:
        # only exit trail if still not a deep loser fee-true (owner: no panic dump)
        if float(ev.get("net_usd") or 0) >= 0:
            return Intent(
                action="exit",
                side=side,
                order_action="sell",
                price=0.01,
                quantity=state.open_qty,
                reduce_only=True,
                reason="trail_giveback_green",
                strategy_id=state.strategy_id,
            )
    if time_stop and secs is not None and secs < NO_ENTRY_SECS and float(ev.get("net_usd") or 0) >= min_edge:
        return Intent(
            action="exit",
            side=side,
            order_action="sell",
            price=0.01,
            quantity=state.open_qty,
            reduce_only=True,
            reason="late_window_bank_green",
            strategy_id=state.strategy_id,
        )
    return Intent(action="hold", side=side, reason="hold_open", strategy_id=state.strategy_id)


def side_executable_prices(book: dict[str, Any]) -> dict[str, Optional[float]]:
    """Executable side prices (YES-scale for yes; side units for no).

    ask_yes = yes_ask
    bid_yes = yes_bid
    ask_no  = 1 - yes_bid
    bid_no  = 1 - yes_ask
    """
    bbo = _bbo(book)
    yb, ya = bbo["yes_bid"], bbo["yes_ask"]
    return {
        "ask_yes": float(ya) if ya is not None else None,
        "bid_yes": float(yb) if yb is not None else None,
        "ask_no": clamp_price(1.0 - float(yb)) if yb is not None else None,
        "bid_no": clamp_price(1.0 - float(ya)) if ya is not None else None,
    }


def _enter(
    side: str,
    book: dict[str, Any],
    state: ArmState,
    *,
    reason: str,
    post_only: bool = False,
    field: Optional[dict[str, Any]] = None,
) -> Intent:
    """Taker lifts ask; post-only rests at or inside bid (never crosses)."""
    bbo = _bbo(book)
    # r1711: never emit a fade against a strong live regime
    rg = regime_gate(side=side, yes_mid=bbo.get("yes_mid"), field=field)
    if rg:
        state.no_trade_reasons.append(rg)
        return Intent(
            action="no_trade",
            reason=rg,
            strategy_id=state.strategy_id,
            side=side,
        )
    px_map = side_executable_prices(book)
    if side == "yes":
        if post_only:
            # post_buy_yes <= yes_bid
            raw = px_map["bid_yes"]
            if raw is None:
                return Intent(
                    action="no_trade",
                    reason="no_post_only_bid",
                    strategy_id=state.strategy_id,
                )
            px = clamp_price(float(raw))
        else:
            raw = px_map["ask_yes"]
            if raw is None:
                raw = bbo["yes_mid"]
            if raw is None:
                return Intent(
                    action="no_trade",
                    reason="no_entry_quote",
                    strategy_id=state.strategy_id,
                )
            px = clamp_price(float(raw))
    else:
        if post_only:
            # post_buy_no <= no_bid = 1 - yes_ask
            raw = px_map["bid_no"]
            if raw is None:
                return Intent(
                    action="no_trade",
                    reason="no_post_only_no_bid",
                    strategy_id=state.strategy_id,
                )
            px = clamp_price(float(raw))
        else:
            # lift no ask = 1 - yes_bid
            raw = px_map["ask_no"]
            if raw is None:
                mid = bbo["yes_mid"]
                raw = clamp_price(1.0 - float(mid)) if mid is not None else None
            if raw is None:
                return Intent(
                    action="no_trade",
                    reason="no_entry_quote",
                    strategy_id=state.strategy_id,
                )
            px = clamp_price(float(raw))
    return Intent(
        action="enter",
        side=side,
        order_action="buy",
        price=px,
        quantity=1.0,
        tif="ioc" if not post_only else "gtc",
        post_only=post_only,
        reason=reason,
        strategy_id=state.strategy_id,
    )


# ── Strategy arms ──────────────────────────────────────────────────────────


def _control_entry_side(book: dict[str, Any]) -> str:
    mid = float(_bbo(book)["yes_mid"] or 0.5)
    return "yes" if mid >= 0.55 else "no"


class EndOfTapeLiquidation:
    """Control: one entry, no TP; force-sell residual at last executable bid.

    This is end-of-tape liquidation — NOT binary settlement.
    """

    strategy_id = "end_of_tape_liquidation"
    version = STRATEGY_VERSION
    settle_mode = "end_of_tape_liquidation"

    def decide(
        self,
        book: dict[str, Any],
        *,
        state: ArmState,
        field: Optional[dict[str, Any]] = None,
    ) -> Intent:
        state.strategy_id = self.strategy_id
        if state.open_qty > 1e-12:
            secs = _secs(book)
            if secs is not None and secs <= 0:
                return Intent(
                    action="flatten",
                    side=state.open_side,
                    order_action="sell",
                    price=0.01,
                    quantity=state.open_qty,
                    reduce_only=True,
                    reason="end_of_tape_flatten",
                    strategy_id=self.strategy_id,
                )
            return Intent(
                action="hold", reason="hold_for_eot_liq", strategy_id=self.strategy_id
            )
        rej = shared_entry_gates(book, state)
        if rej:
            state.no_trade_reasons.append(rej)
            return Intent(action="no_trade", reason=rej, strategy_id=self.strategy_id)
        side = _control_entry_side(book)
        return _enter(side, book, state, reason="eot_liq_entry", field=field)


class HoldToSettlement:
    """Control: one entry, hold to binary resolution (0/1 payoff, no exit trade).

    Eligible only when lab has a canonical resolved outcome. Never substitutes
    last quote for settlement.
    """

    strategy_id = "hold_to_settlement"
    version = STRATEGY_VERSION
    settle_mode = "hold_to_settlement"

    def decide(
        self,
        book: dict[str, Any],
        *,
        state: ArmState,
        field: Optional[dict[str, Any]] = None,
    ) -> Intent:
        state.strategy_id = self.strategy_id
        if state.open_qty > 1e-12:
            # Never force-sell at last quote — lab settles via resolved outcome.
            return Intent(
                action="hold", reason="hold_to_settlement", strategy_id=self.strategy_id
            )
        rej = shared_entry_gates(book, state)
        if rej:
            state.no_trade_reasons.append(rej)
            return Intent(action="no_trade", reason=rej, strategy_id=self.strategy_id)
        side = _control_entry_side(book)
        return _enter(side, book, state, reason="hold_to_settlement_entry", field=field)


# Backward-compat alias (deprecated name for end-of-tape liquidation)
HoldBaseline = EndOfTapeLiquidation


class TakerMomentumTP:
    """Enter on short momentum + spread/depth; exit fee-true TP / trail / time."""

    strategy_id = "taker_momentum_tp"
    version = STRATEGY_VERSION

    def decide(
        self,
        book: dict[str, Any],
        *,
        state: ArmState,
        field: Optional[dict[str, Any]] = None,
    ) -> Intent:
        state.strategy_id = self.strategy_id
        ex = _exit_if_open(book, state)
        if ex is not None and ex.action != "hold":
            return ex
        if state.open_qty > 1e-12:
            return ex or Intent(action="hold", reason="hold_open")
        rej = shared_entry_gates(book, state)
        if rej:
            state.no_trade_reasons.append(rej)
            return Intent(action="no_trade", reason=rej, strategy_id=self.strategy_id)
        bbo = _bbo(book)
        mid = float(bbo["yes_mid"] or 0.5)
        mom = float((field or {}).get("mom_yes") or 0.0)
        # need clear direction momentum
        if abs(mom) < 0.015:
            state.no_trade_reasons.append("weak_momentum")
            return Intent(action="no_trade", reason="weak_momentum", strategy_id=self.strategy_id)
        side = "yes" if mom > 0 else "no"
        # avoid chasing extreme
        if side == "yes" and mid > 0.88:
            return Intent(action="no_trade", reason="too_rich_yes", strategy_id=self.strategy_id)
        if side == "no" and mid < 0.12:
            return Intent(action="no_trade", reason="too_rich_no", strategy_id=self.strategy_id)
        return _enter(side, book, state, reason="momentum_entry", field=field)


class PullbackContinuation:
    """Confirmed direction + pullback toward micro-VWAP, then continuation."""

    strategy_id = "pullback_continuation"
    version = STRATEGY_VERSION

    def decide(
        self,
        book: dict[str, Any],
        *,
        state: ArmState,
        field: Optional[dict[str, Any]] = None,
    ) -> Intent:
        state.strategy_id = self.strategy_id
        ex = _exit_if_open(book, state, trail_giveback=0.015)
        if ex is not None and ex.action != "hold":
            return ex
        if state.open_qty > 1e-12:
            return ex or Intent(action="hold", reason="hold_open")
        rej = shared_entry_gates(book, state)
        if rej:
            state.no_trade_reasons.append(rej)
            return Intent(action="no_trade", reason=rej, strategy_id=self.strategy_id)
        f = field or {}
        trend = float(f.get("trend_yes") or 0.0)
        vwap = f.get("micro_vwap_yes")
        mid = float(_bbo(book)["yes_mid"] or 0.5)
        if abs(trend) < 0.01:
            return Intent(action="no_trade", reason="no_trend", strategy_id=self.strategy_id)
        side = "yes" if trend > 0 else "no"
        if vwap is None:
            # without vwap, require mild pullback via mom reverse of trend
            mom = float(f.get("mom_yes") or 0.0)
            if trend > 0 and mom > -0.005:
                return Intent(action="no_trade", reason="no_pullback", strategy_id=self.strategy_id)
            if trend < 0 and mom < 0.005:
                return Intent(action="no_trade", reason="no_pullback", strategy_id=self.strategy_id)
        else:
            v = float(vwap)
            if side == "yes" and mid > v - 0.005:
                return Intent(action="no_trade", reason="no_pullback_to_vwap", strategy_id=self.strategy_id)
            if side == "no" and mid < v + 0.005:
                return Intent(action="no_trade", reason="no_pullback_to_vwap", strategy_id=self.strategy_id)
        return _enter(side, book, state, reason="pullback_cont_entry", field=field)


class MicroMeanReversion:
    """Fade short-lived displacement with two-sided depth; not settlement fade."""

    strategy_id = "micro_mean_reversion"
    version = STRATEGY_VERSION

    def decide(
        self,
        book: dict[str, Any],
        *,
        state: ArmState,
        field: Optional[dict[str, Any]] = None,
    ) -> Intent:
        state.strategy_id = self.strategy_id
        ex = _exit_if_open(book, state, min_edge=0.025, trail_giveback=0.012)
        if ex is not None and ex.action != "hold":
            return ex
        if state.open_qty > 1e-12:
            return ex or Intent(action="hold", reason="hold_open")
        rej = shared_entry_gates(book, state)
        if rej:
            state.no_trade_reasons.append(rej)
            return Intent(action="no_trade", reason=rej, strategy_id=self.strategy_id)
        bbo = _bbo(book)
        if float(bbo["bid_sz"] or 0) < 1.0 or float(bbo["ask_sz"] or 0) < 1.0:
            return Intent(action="no_trade", reason="need_two_sided_depth", strategy_id=self.strategy_id)
        mom = float((field or {}).get("mom_yes") or 0.0)
        # fade only sharp short displacement
        if abs(mom) < 0.03:
            return Intent(action="no_trade", reason="no_displacement", strategy_id=self.strategy_id)
        if abs(mom) > 0.10:
            return Intent(action="no_trade", reason="displacement_too_large", strategy_id=self.strategy_id)
        side = "no" if mom > 0 else "yes"  # fade
        mid = float(bbo["yes_mid"] or 0.5)
        # only near mid band (not settlement extremes)
        if mid > 0.80 or mid < 0.20:
            return Intent(action="no_trade", reason="outside_micro_band", strategy_id=self.strategy_id)
        return _enter(side, book, state, reason="micro_mr_fade", field=field)


class MakerSpreadCapture:
    """Post-only around fair value — shadow until queue calibration credible."""

    strategy_id = "maker_spread_capture"
    version = STRATEGY_VERSION
    shadow_only = True

    def decide(
        self,
        book: dict[str, Any],
        *,
        state: ArmState,
        field: Optional[dict[str, Any]] = None,
    ) -> Intent:
        state.strategy_id = self.strategy_id
        # P0.8: one resting order max — do not spam GTC
        if state.open_order_id and state.open_qty <= 1e-12:
            return Intent(
                action="hold",
                reason="maker_resting_await_fill",
                strategy_id=self.strategy_id,
            )
        if state.open_qty > 1e-12:
            if state.open_order_id and state.open_order_action == "sell":
                return Intent(
                    action="hold", reason="maker_exit_resting", strategy_id=self.strategy_id
                )
            ex = _exit_if_open(book, state, min_edge=0.02)
            if ex and ex.action in ("exit", "flatten"):
                intent = ex
                intent.post_only = True
                intent.tif = "gtc"
                # post_sell_side >= side_ask (never cross)
                px_map = side_executable_prices(book)
                if intent.side == "yes" and px_map["ask_yes"] is not None:
                    intent.price = clamp_price(float(px_map["ask_yes"]))
                elif intent.side == "no" and px_map["ask_no"] is not None:
                    intent.price = clamp_price(float(px_map["ask_no"]))
                return intent
            return Intent(action="hold", reason="maker_hold", strategy_id=self.strategy_id)
        rej = shared_entry_gates(book, state)
        if rej:
            return Intent(action="no_trade", reason=rej, strategy_id=self.strategy_id)
        bbo = _bbo(book)
        spread = bbo["spread"]
        if spread is None or spread < 0.02:
            return Intent(
                action="no_trade",
                reason="spread_too_tight_for_maker",
                strategy_id=self.strategy_id,
            )
        mid = float(bbo["yes_mid"] or 0.5)
        side = "yes" if mid >= 0.5 else "no"
        return _enter(side, book, state, reason="maker_post_only", post_only=True, field=field)


class CrossAssetConfirmation:
    """BTC/ETH/SOL field breadth as entry filter for one asset only."""

    strategy_id = "cross_asset_confirmation"
    version = STRATEGY_VERSION

    def decide(
        self,
        book: dict[str, Any],
        *,
        state: ArmState,
        field: Optional[dict[str, Any]] = None,
    ) -> Intent:
        state.strategy_id = self.strategy_id
        ex = _exit_if_open(book, state)
        if ex is not None and ex.action != "hold":
            return ex
        if state.open_qty > 1e-12:
            return ex or Intent(action="hold", reason="hold_open")
        rej = shared_entry_gates(book, state)
        if rej:
            return Intent(action="no_trade", reason=rej, strategy_id=self.strategy_id)
        f = field or {}
        breadth = f.get("majors_breadth")  # -1..+1 fraction up
        if breadth is None:
            return Intent(action="no_trade", reason="no_breadth", strategy_id=self.strategy_id)
        b = float(breadth)
        if abs(b) < 0.6:
            return Intent(action="no_trade", reason="weak_field_breadth", strategy_id=self.strategy_id)
        side = "yes" if b > 0 else "no"
        # one asset only — never open correlated basket inside arm
        return _enter(side, book, state, reason="cross_asset_confirm", field=field)


def all_strategies() -> list[Any]:
    return [
        EndOfTapeLiquidation(),
        HoldToSettlement(),
        TakerMomentumTP(),
        PullbackContinuation(),
        MicroMeanReversion(),
        MakerSpreadCapture(),
        CrossAssetConfirmation(),
    ]


def strategy_registry() -> dict[str, Any]:
    return {s.strategy_id: s for s in all_strategies()}


def policy_hash_for_strategies() -> str:
    blob = "|".join(f"{s.strategy_id}:{s.version}" for s in all_strategies())
    return hashlib.sha256(f"{blob}|{STRATEGY_VERSION}".encode()).hexdigest()[:16]


def feature_field_from_books(
    history: list[dict[str, Any]],
    *,
    majors_mids: Optional[dict[str, float]] = None,
    majors_prev_mids: Optional[dict[str, float]] = None,
    majors_ts: Optional[dict[str, int]] = None,
) -> dict[str, Any]:
    """Point-in-time features only — majors maps must be as-of decision time (no lookahead).

    Breadth from co-movement (returns) at t vs prior sample — not level>=0.55 at end.
    Requires ≥3 fresh majors for a defined breadth.
    """
    if not history:
        return {}
    mids: list[float] = []
    for b in history:
        bb = _bbo(b)
        if bb["yes_mid"] is not None:
            mids.append(float(bb["yes_mid"]))
    if not mids:
        return {}
    cur = mids[-1]
    mom = cur - mids[-2] if len(mids) >= 2 else 0.0
    window = mids[-5:] if len(mids) >= 5 else mids
    trend = window[-1] - window[0] if len(window) >= 2 else 0.0
    rolling_mid_mean = sum(window) / len(window)
    breadth = None
    breadth_complete = False
    if majors_mids and majors_prev_mids:
        signs: list[float] = []
        for a, mid_t in majors_mids.items():
            mid_p = majors_prev_mids.get(a)
            if mid_p is None:
                continue
            try:
                d = float(mid_t) - float(mid_p)
            except (TypeError, ValueError):
                continue
            if abs(d) < 1e-9:
                continue
            signs.append(1.0 if d > 0 else -1.0)
        if len(signs) >= 3:
            breadth = sum(signs) / len(signs)
            breadth_complete = True
    return {
        "mom_yes": mom,
        "trend_yes": trend,
        "rolling_mid_mean": rolling_mid_mean,
        "micro_vwap_yes": rolling_mid_mean,  # legacy name — not true microprice
        "majors_breadth": breadth,
        "majors_breadth_complete": breadth_complete,
        "n_hist": len(mids),
        "majors_n": len(majors_mids or {}),
        "majors_source_ts": dict(majors_ts or {}),
    }


__all__ = [
    "TRUTH",
    "STRATEGY_VERSION",
    "REGIME_RECEIPT",
    "SALVAGE_RECEIPT",
    "REGIME_GATE_ENABLED",
    "REGIME_GATE_IMPLIED_THRESH",
    "SALVAGE_EXIT_ENABLED",
    "SALVAGE_SIDE_IMPLIED_MAX",
    "SALVAGE_MIN_SECS_LEFT",
    "SALVAGE_EXIT_REASON",
    "SALVAGE_COHORT",
    "SOFT_ADVERSE_ENABLED",
    "SOFT_ADVERSE_SIDE_IMPLIED_MAX",
    "SOFT_ADVERSE_MAX_SECS_LEFT",
    "SOFT_ADVERSE_MAX_LOSS_PER_CONTRACT",
    "SOFT_ADVERSE_REASON",
    "Intent",
    "ArmState",
    "all_strategies",
    "strategy_registry",
    "policy_hash_for_strategies",
    "feature_field_from_books",
    "side_executable_prices",
    "side_implied_prob",
    "salvage_exit_should_fire",
    "salvage_exit_intent",
    "soft_adverse_should_fire",
    "regime_gate",
    "regime_preferred_side",
    "shared_entry_gates",
    "MAX_RT_PER_TICKER_WINDOW",
    "HoldBaseline",
    "EndOfTapeLiquidation",
    "HoldToSettlement",
]
