#!/usr/bin/env python3
"""r1684-c — Deterministic Kalshi-compatible execution simulator (STGM only).

Mirrors V2 semantics for laboratory fills:
  - YES price scale; NO via complement
  - Taker walks observable depth at arrival (after latency)
  - Maker requires trade-through; else fill_unknown (never invent fill)
  - Fees from versioned taker model; ledger-driven cash/inventory
  - Force-flatten open inventory at bid before cutoff or mark unflattenable

Never places real USD. Never imports order transmitters.

Truth: ALICE_15M_EXECUTION_SIM_V1
Receipt: r1684-c-kalshi-execution-sim
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".sifta_state"
TRUTH = "ALICE_15M_EXECUTION_SIM_V1"
RECEIPT = "r1684-c-kalshi-execution-sim"
LEDGER_NAME = "alice_15m_scalp_orders.jsonl"
FEE_MODEL = "taker_0.07_p_(1-p)_ceil_centicent_v1"

# Default latency scenarios (ms)
LATENCY_SCENARIOS_MS = (250, 500, 1000)


def _state(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else p / ".sifta_state"


def estimate_taker_fee(price: float, *, contracts: float = 1.0) -> float:
    from System.alice_15m_scalp_learner import estimate_taker_fee as _f

    return float(_f(price, contracts=contracts))


def clamp_price(p: float) -> float:
    return min(0.99, max(0.01, float(p)))


def parse_levels(levels: Any) -> list[tuple[float, float]]:
    """[[price_str, qty_str], ...] → sorted list of (price, qty)."""
    out: list[tuple[float, float]] = []
    if not levels:
        return out
    for row in levels:
        try:
            if isinstance(row, (list, tuple)) and len(row) >= 2:
                out.append((float(row[0]), float(row[1])))
            elif isinstance(row, dict):
                out.append((float(row.get("price") or row.get("p")), float(row.get("qty") or row.get("q") or 0)))
        except (TypeError, ValueError):
            continue
    return out


def walk_taker_buy_yes(
    yes_asks: list[tuple[float, float]],
    *,
    limit_price: float,
    quantity: float,
) -> tuple[list[dict[str, float]], float]:
    """Buy YES walking asks ascending until qty filled or limit breached.

    Returns (fills, unfilled_qty).
    """
    fills: list[dict[str, float]] = []
    rem = float(quantity)
    asks = sorted(yes_asks, key=lambda x: x[0])
    for px, qty in asks:
        if rem <= 1e-12:
            break
        if px > float(limit_price) + 1e-12:
            break
        take = min(rem, qty)
        if take <= 0:
            continue
        fills.append({"price": clamp_price(px), "qty": take})
        rem -= take
    return fills, rem


def walk_taker_sell_yes(
    yes_bids: list[tuple[float, float]],
    *,
    limit_price: float,
    quantity: float,
) -> tuple[list[dict[str, float]], float]:
    """Sell YES (or buy NO as sell YES) walking bids descending."""
    fills: list[dict[str, float]] = []
    rem = float(quantity)
    bids = sorted(yes_bids, key=lambda x: -x[0])
    for px, qty in bids:
        if rem <= 1e-12:
            break
        if px < float(limit_price) - 1e-12:
            break
        take = min(rem, qty)
        if take <= 0:
            continue
        fills.append({"price": clamp_price(px), "qty": take})
        rem -= take
    return fills, rem


@dataclass
class SimOrder:
    order_id: str
    ticker: str
    side: str  # "yes" | "no"
    action: str  # "buy" | "sell"
    price: float  # YES-scale price for V2
    quantity: float
    tif: str = "ioc"  # ioc | fok | gtc
    post_only: bool = False
    reduce_only: bool = False
    strategy_id: str = ""
    run_id: str = ""
    window_id: str = ""
    submitted_ts_ms: int = 0
    arrival_ts_ms: int = 0
    latency_ms: int = 0
    state: str = "submitted"
    filled_qty: float = 0.0
    remaining_qty: float = 0.0
    avg_fill_price: float = 0.0
    fees_paid: float = 0.0
    fills: list[dict[str, Any]] = field(default_factory=list)
    fill_confidence: str = "unknown"  # filled | partial | no_fill | fill_unknown
    reason: str = ""


@dataclass
class Position:
    ticker: str
    side: str  # net long yes or no
    qty: float = 0.0
    avg_entry: float = 0.0
    fees_entry: float = 0.0
    realized_pnl: float = 0.0
    mfe: float = 0.0  # max favorable excursion (side units)
    mae: float = 0.0  # max adverse excursion


class KalshiExecutionSim:
    """One simulator instance per run_id / latency scenario."""

    def __init__(
        self,
        *,
        run_id: Optional[str] = None,
        latency_ms: int = 500,
        state_dir: Optional[Path | str] = None,
        strategy_id: str = "",
        policy_hash: str = "",
        persist: bool = True,
    ) -> None:
        self.run_id = run_id or f"sim-{uuid.uuid4().hex[:10]}"
        self.latency_ms = int(latency_ms)
        self.root = _state(state_dir)
        self.strategy_id = strategy_id
        self.policy_hash = policy_hash
        self.persist = persist
        self.orders: dict[str, SimOrder] = {}
        self.positions: dict[str, Position] = {}
        self.cash: float = 0.0
        self.realized_pnl: float = 0.0
        self.fees_total: float = 0.0
        self.events: list[dict[str, Any]] = []
        self._books: dict[str, dict[str, Any]] = {}  # ticker → latest book
        # P0.2: full per-ticker tape for book-at-arrival (not decision book)
        self._tape: dict[str, list[dict[str, Any]]] = {}
        self._clock_ms: int = 0
        self.n_no_fills = 0
        self.n_fills = 0
        self.n_partial = 0
        self.n_unflattenable = 0
        self.n_no_arrival_book = 0

    def _ledger(self, row: dict[str, Any]) -> None:
        row = dict(row)
        row.setdefault("run_id", self.run_id)
        row.setdefault("strategy_id", self.strategy_id)
        row.setdefault("policy_hash", self.policy_hash)
        row.setdefault("latency_ms", self.latency_ms)
        row.setdefault("truth_label", TRUTH)
        row.setdefault("receipt_id", RECEIPT)
        row.setdefault("fee_model", FEE_MODEL)
        row.setdefault("ts", time.time())
        row.setdefault("usd", False)
        self.events.append(row)
        if not self.persist:
            return
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            with (self.root / LEDGER_NAME).open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        except OSError:
            pass

    @staticmethod
    def _event_ts_ms(event: dict[str, Any]) -> int:
        return int(
            event.get("exchange_ts_ms")
            or event.get("recv_ts_ms")
            or event.get("ts_ms")
            or 0
        )

    def register_tape(self, ticker: str, books: list[dict[str, Any]]) -> None:
        """Preload chronological books for a ticker (P0.2 arrival lookup)."""
        t = str(ticker or "")
        if not t:
            return
        ordered = sorted(books, key=lambda b: (self._event_ts_ms(b), int(b.get("seq") or 0)))
        self._tape[t] = [dict(b) for b in ordered]
        if ordered:
            self._books[t] = dict(ordered[-1])

    def book_at_arrival(
        self, ticker: str, arrival_ts_ms: int
    ) -> Optional[dict[str, Any]]:
        """First complete book with event_ts >= arrival_ts_ms; else None."""
        books = self._tape.get(str(ticker) or "") or []
        if not books:
            # fallback: only latest if already at/after arrival
            cur = self._books.get(str(ticker) or "")
            if cur and self._event_ts_ms(cur) >= int(arrival_ts_ms):
                return dict(cur)
            return None
        for b in books:
            if self._event_ts_ms(b) >= int(arrival_ts_ms):
                return dict(b)
        return None

    def on_book(self, event: dict[str, Any]) -> list[dict[str, Any]]:
        """Update book; process resting GTC if any (maker path conservative)."""
        ticker = str(event.get("ticker") or "")
        if not ticker:
            return []
        recv = self._event_ts_ms(event)
        if recv:
            self._clock_ms = max(self._clock_ms, recv)
        self._books[ticker] = dict(event)
        # append to tape if not already registered as a full hist
        hist = self._tape.setdefault(ticker, [])
        if not hist or self._event_ts_ms(hist[-1]) != recv or hist[-1] is not event:
            # avoid exact duplicate consecutive push of same object
            if not hist or hist[-1] != event:
                hist.append(dict(event))
        results: list[dict[str, Any]] = []
        # Attempt maker fills only if trade event or aggressive book cross
        for oid, order in list(self.orders.items()):
            if order.state not in ("resting", "partial"):
                continue
            if order.ticker != ticker:
                continue
            if order.post_only or order.tif == "gtc":
                fill_evt = self._try_maker_fill(order, event)
                if fill_evt:
                    results.append(fill_evt)
        return results

    def submit(self, order: dict[str, Any]) -> dict[str, Any]:
        """Submit simulated order. Taker fills against book AT ARRIVAL after latency.

        P0.2: latency changes the arrival book. Callers must not inject the
        decision book as arrival truth except explicit unit fixtures
        (``book_at_arrival`` key present).
        """
        now = int(order.get("submitted_ts_ms") or self._clock_ms or int(time.time() * 1000))
        latency = int(order.get("latency_ms", self.latency_ms))
        arrival = now + latency
        oid = str(order.get("order_id") or f"o-{uuid.uuid4().hex[:12]}")
        side = str(order.get("side") or "yes").lower()
        action = str(order.get("action") or "buy").lower()
        # V2 yes-scale price
        price = clamp_price(float(order.get("price") or order.get("yes_price") or 0.5))
        qty = float(order.get("quantity") or order.get("count") or 1.0)
        tif = str(order.get("tif") or order.get("time_in_force") or "ioc").lower()
        post_only = bool(order.get("post_only") or False)
        reduce_only = bool(order.get("reduce_only") or False)
        ticker = str(order.get("ticker") or "")
        so = SimOrder(
            order_id=oid,
            ticker=ticker,
            side=side,
            action=action,
            price=price,
            quantity=qty,
            tif=tif,
            post_only=post_only,
            reduce_only=reduce_only,
            strategy_id=str(order.get("strategy_id") or self.strategy_id),
            run_id=self.run_id,
            window_id=str(order.get("window_id") or ""),
            submitted_ts_ms=now,
            arrival_ts_ms=arrival,
            latency_ms=latency,
            remaining_qty=qty,
        )
        self.orders[oid] = so
        self._ledger(
            {
                "event": "order_submitted",
                "order_id": oid,
                "ticker": ticker,
                "side": side,
                "action": action,
                "price": price,
                "quantity": qty,
                "tif": tif,
                "post_only": post_only,
                "reduce_only": reduce_only,
                "submitted_ts_ms": now,
                "arrival_ts_ms": arrival,
                "window_id": so.window_id,
                "state": "submitted",
            }
        )
        # P0.2: book at arrival from tape unless unit fixture injects book_at_arrival
        if "book_at_arrival" in order and order.get("book_at_arrival") is not None:
            book = order.get("book_at_arrival")
        else:
            book = self.book_at_arrival(ticker, arrival)
            if book is None and latency <= 0:
                # zero-latency fallback: decision-time book already on_book'd
                book = self._books.get(ticker)
        if post_only or tif == "gtc":
            so.state = "resting"
            so.fill_confidence = "fill_unknown" if post_only else "unknown"
            so.reason = "resting_maker_awaits_trade_through"
            self._ledger(
                {
                    "event": "order_resting",
                    "order_id": oid,
                    "ticker": ticker,
                    "state": "resting",
                    "fill_confidence": so.fill_confidence,
                    "reason": so.reason,
                }
            )
            return self._order_snapshot(so)

        if not book:
            so.state = "rejected"
            so.fill_confidence = "no_fill"
            so.reason = "no_arrival_book"
            self.n_no_fills += 1
            self.n_no_arrival_book += 1
            self._ledger(
                {
                    "event": "order_rejected",
                    "order_id": oid,
                    "ticker": ticker,
                    "state": "rejected",
                    "reason": so.reason,
                    "fill_confidence": "no_fill",
                    "arrival_ts_ms": arrival,
                }
            )
            return self._order_snapshot(so)

        return self._match_taker(so, book)

    def _match_taker(self, so: SimOrder, book: dict[str, Any]) -> dict[str, Any]:
        yes_bids = parse_levels(book.get("yes_bids"))
        no_bids = parse_levels(book.get("no_bids"))
        # derive asks from complement if missing
        yes_asks = parse_levels(book.get("yes_asks"))
        if not yes_asks and no_bids:
            yes_asks = sorted([(clamp_price(1.0 - p), q) for p, q in no_bids], key=lambda x: x[0])
        no_asks = parse_levels(book.get("no_asks"))
        if not no_asks and yes_bids:
            no_asks = sorted([(clamp_price(1.0 - p), q) for p, q in yes_bids], key=lambda x: x[0])

        # Map side/action → walk on YES book
        # buy yes → lift asks; sell yes → hit bids
        # buy no → lift no asks ≡ hit yes bids at 1-p; sell no → hit no bids ≡ lift yes asks
        fills: list[dict[str, float]] = []
        rem = so.quantity

        if so.side == "yes" and so.action == "buy":
            fills, rem = walk_taker_buy_yes(yes_asks, limit_price=so.price, quantity=so.quantity)
        elif so.side == "yes" and so.action == "sell":
            fills, rem = walk_taker_sell_yes(yes_bids, limit_price=so.price, quantity=so.quantity)
        elif so.side == "no" and so.action == "buy":
            # buy NO at no_price; V2 yes-price for buy no is often the yes price of the order
            # Walk no asks: price_no = so.price if order priced in no-space, else 1-so.price
            # Convention: so.price is YES-scale limit for the order (V2). Buy NO limit yes_px means
            # willing to pay no up to (1 - yes_px)? Kalshi V2 uses yes price + side.
            # We treat so.price as the max YES price when buying NO... simpler lab rule:
            # side_price = so.price is the price of the contract side being bought.
            # Convert: buy NO at side_price p → equivalent yes_bid walk at 1-p for selling yes.
            # Actually: buying NO at price p means paying p for NO. Executable no ask = 1 - yes_bid.
            no_limit = so.price  # price of NO contract
            # Walk no_asks sorted ascending
            no_asks_sorted = sorted(no_asks, key=lambda x: x[0]) if no_asks else [
                (clamp_price(1.0 - p), q) for p, q in yes_bids
            ]
            fills = []
            rem = so.quantity
            for px, qty in no_asks_sorted:
                if rem <= 1e-12:
                    break
                if px > no_limit + 1e-12:
                    break
                take = min(rem, qty)
                fills.append({"price": clamp_price(px), "qty": take})  # NO-side fill prices
                rem -= take
        else:  # sell no
            no_limit = so.price
            no_bids_sorted = sorted(no_bids, key=lambda x: -x[0]) if no_bids else [
                (clamp_price(1.0 - p), q) for p, q in yes_asks
            ]
            fills = []
            rem = so.quantity
            for px, qty in no_bids_sorted:
                if rem <= 1e-12:
                    break
                if px < no_limit - 1e-12:
                    break
                take = min(rem, qty)
                fills.append({"price": clamp_price(px), "qty": take})
                rem -= take

        if so.tif == "fok" and rem > 1e-12:
            so.state = "canceled"
            so.fill_confidence = "no_fill"
            so.reason = "fok_incomplete"
            so.remaining_qty = so.quantity
            self.n_no_fills += 1
            self._ledger(
                {
                    "event": "order_canceled",
                    "order_id": so.order_id,
                    "ticker": so.ticker,
                    "state": "canceled",
                    "reason": so.reason,
                    "fill_confidence": "no_fill",
                }
            )
            return self._order_snapshot(so)

        if not fills:
            so.state = "canceled" if so.tif == "ioc" else "resting"
            so.fill_confidence = "no_fill"
            so.reason = "no_liquidity_at_limit"
            so.remaining_qty = so.quantity
            self.n_no_fills += 1
            self._ledger(
                {
                    "event": "order_no_fill",
                    "order_id": so.order_id,
                    "ticker": so.ticker,
                    "state": so.state,
                    "reason": so.reason,
                    "fill_confidence": "no_fill",
                }
            )
            return self._order_snapshot(so)

        self._apply_fills(so, fills, rem)
        return self._order_snapshot(so)

    def _apply_fills(
        self, so: SimOrder, fills: list[dict[str, float]], rem: float
    ) -> None:
        filled = sum(f["qty"] for f in fills)
        notional = sum(f["price"] * f["qty"] for f in fills)
        avg = notional / filled if filled > 0 else 0.0
        fee = 0.0
        for f in fills:
            fee += estimate_taker_fee(f["price"], contracts=f["qty"])
        fee = round(fee, 4)
        so.fills.extend(fills)
        so.filled_qty = round(so.filled_qty + filled, 6)
        so.remaining_qty = max(0.0, rem)
        so.avg_fill_price = clamp_price(avg)
        so.fees_paid = round(so.fees_paid + fee, 4)
        so.fill_confidence = "partial" if rem > 1e-12 else "filled"
        so.state = "partial" if rem > 1e-12 else "filled"
        if so.tif == "ioc" and rem > 1e-12:
            so.state = "partial"  # remainder canceled on IOC
            so.remaining_qty = 0.0  # IOC cancels rest
            so.reason = "ioc_partial"
        self.fees_total = round(self.fees_total + fee, 4)
        if so.fill_confidence == "partial":
            self.n_partial += 1
        else:
            self.n_fills += 1
        self._update_position(so, filled, avg, fee)
        self._ledger(
            {
                "event": "order_fill",
                "order_id": so.order_id,
                "ticker": so.ticker,
                "side": so.side,
                "action": so.action,
                "fill_qty": filled,
                "avg_fill_price": avg,
                "fee": fee,
                "remaining_qty": so.remaining_qty,
                "state": so.state,
                "fill_confidence": so.fill_confidence,
                "fills": fills,
                "position_after": self._pos_dict(so.ticker),
                "realized_pnl": self.realized_pnl,
                "cash": self.cash,
            }
        )

    def _update_position(
        self, so: SimOrder, qty: float, avg: float, fee: float
    ) -> None:
        key = so.ticker
        pos = self.positions.get(key)
        if so.action == "buy":
            # open / add long on side
            if pos is None or pos.qty <= 1e-12:
                self.positions[key] = Position(
                    ticker=key,
                    side=so.side,
                    qty=qty,
                    avg_entry=avg,
                    fees_entry=fee,
                )
                self.cash = round(self.cash - avg * qty - fee, 6)
            elif pos.side == so.side:
                new_q = pos.qty + qty
                pos.avg_entry = (pos.avg_entry * pos.qty + avg * qty) / new_q
                pos.qty = new_q
                pos.fees_entry = round(pos.fees_entry + fee, 4)
                self.cash = round(self.cash - avg * qty - fee, 6)
            else:
                # reducing opposite side
                self._close_qty(pos, qty, avg, fee)
        else:
            # sell = reduce or open short-side (lab: only reduce_only sells open)
            if pos is None or pos.qty <= 1e-12:
                if so.reduce_only:
                    so.reason = "reduce_only_no_position"
                    return
                # open opposite as new long on other side
                self.positions[key] = Position(
                    ticker=key,
                    side=so.side,
                    qty=qty,
                    avg_entry=avg,
                    fees_entry=fee,
                )
                self.cash = round(self.cash - avg * qty - fee, 6)
            else:
                self._close_qty(pos, qty, avg, fee)

    def _close_qty(self, pos: Position, qty: float, exit_px: float, fee: float) -> None:
        close_q = min(pos.qty, qty)
        # side PnL: long yes/no at avg_entry, exit at exit_px (same side units)
        gross = (exit_px - pos.avg_entry) * close_q
        # allocate entry fee pro-rata
        entry_fee_share = pos.fees_entry * (close_q / pos.qty) if pos.qty > 0 else 0.0
        net = round(gross - entry_fee_share - fee, 4)
        pos.realized_pnl = round(pos.realized_pnl + net, 4)
        self.realized_pnl = round(self.realized_pnl + net, 4)
        self.cash = round(self.cash + exit_px * close_q - fee, 6)
        pos.qty = round(pos.qty - close_q, 6)
        pos.fees_entry = round(pos.fees_entry - entry_fee_share, 4)
        if pos.qty <= 1e-12:
            pos.qty = 0.0

    def _try_maker_fill(self, so: SimOrder, event: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Maker fills only on explicit trade-through; else leave resting / fill_unknown."""
        trade_px = event.get("trade_price")
        trade_sz = event.get("trade_size")
        if trade_px is None or trade_sz is None:
            # no trade print → cannot claim maker fill
            return None
        try:
            tpx = float(trade_px)
            tsz = float(trade_sz)
        except (TypeError, ValueError):
            return None
        # Conservative: require trade through our level
        if so.action == "buy" and tpx > so.price + 1e-12:
            return None
        if so.action == "sell" and tpx < so.price - 1e-12:
            return None
        take = min(so.remaining_qty or so.quantity - so.filled_qty, tsz * 0.25)  # queue-ahead haircut
        if take <= 1e-12:
            return None
        fills = [{"price": clamp_price(so.price), "qty": take}]
        rem = (so.remaining_qty or so.quantity - so.filled_qty) - take
        self._apply_fills(so, fills, max(0.0, rem))
        so.fill_confidence = "filled" if rem <= 1e-12 else "partial"
        return self._order_snapshot(so)

    def cancel(self, order_id: str) -> dict[str, Any]:
        so = self.orders.get(order_id)
        if not so:
            return {"ok": False, "reason": "unknown_order"}
        if so.state in ("filled", "canceled", "rejected"):
            return self._order_snapshot(so)
        so.state = "canceled"
        so.reason = so.reason or "canceled"
        self._ledger(
            {
                "event": "order_canceled",
                "order_id": order_id,
                "ticker": so.ticker,
                "state": "canceled",
                "filled_qty": so.filled_qty,
                "remaining_qty": so.remaining_qty,
            }
        )
        return self._order_snapshot(so)

    def amend(self, order_id: str, *, price: float, quantity: float) -> dict[str, Any]:
        so = self.orders.get(order_id)
        if not so or so.state not in ("resting", "partial", "submitted"):
            return {"ok": False, "reason": "not_amendable"}
        so.price = clamp_price(price)
        so.quantity = float(quantity)
        so.remaining_qty = float(quantity) - so.filled_qty
        self._ledger(
            {
                "event": "order_amended",
                "order_id": order_id,
                "ticker": so.ticker,
                "price": so.price,
                "quantity": so.quantity,
                "state": so.state,
            }
        )
        return self._order_snapshot(so)

    def mark_excursions(self, ticker: str, mark_side_px: float) -> None:
        pos = self.positions.get(ticker)
        if not pos or pos.qty <= 0:
            return
        fav = mark_side_px - pos.avg_entry
        pos.mfe = max(pos.mfe, fav)
        pos.mae = min(pos.mae, fav)

    def force_flatten(
        self,
        ticker: str,
        *,
        book: Optional[dict[str, Any]] = None,
        reason: str = "cutoff_flatten",
    ) -> dict[str, Any]:
        """Force close at observable bid; unflattenable if no depth."""
        pos = self.positions.get(ticker)
        if not pos or pos.qty <= 1e-12:
            return {"ok": True, "n_closed": 0}
        book = book or self._books.get(ticker)
        if not book:
            self.n_unflattenable += 1
            self._ledger(
                {
                    "event": "unflattenable",
                    "ticker": ticker,
                    "qty": pos.qty,
                    "side": pos.side,
                    "reason": "no_book",
                    "state": "unflattenable",
                }
            )
            return {"ok": False, "reason": "unflattenable_no_book", "qty": pos.qty}

        # sell our side at bid
        side_price_for_order = 0.01  # aggressive
        # Flatten is an end-of-tape action: use provided book as arrival fixture
        # (decision book == last tape book; latency already absorbed by hist end).
        snap = self.submit(
            {
                "ticker": ticker,
                "side": pos.side,
                "action": "sell",
                "price": side_price_for_order if pos.side == "yes" else side_price_for_order,
                "quantity": pos.qty,
                "tif": "ioc",
                "reduce_only": True,
                "book_at_arrival": book,
                "latency_ms": 0,
                "submitted_ts_ms": self._event_ts_ms(book) or self._clock_ms,
                "window_id": str(book.get("window_id") or ""),
                "strategy_id": self.strategy_id,
            }
        )
        remaining = float((self.positions.get(ticker).qty if self.positions.get(ticker) else 0) or 0)
        if (
            snap.get("fill_confidence") in ("no_fill", "fill_unknown")
            or float(snap.get("filled_qty") or 0) <= 0
            or remaining > 1e-12
        ):
            # P0.4: partial/failed flatten leaves residual inventory charged
            if remaining > 1e-12 or float(snap.get("filled_qty") or 0) <= 0:
                self.n_unflattenable += 1
                self._ledger(
                    {
                        "event": "unflattenable",
                        "ticker": ticker,
                        "qty": remaining if remaining > 1e-12 else pos.qty,
                        "side": pos.side,
                        "reason": reason,
                        "state": "unflattenable",
                        "partial_fill": float(snap.get("filled_qty") or 0) > 0,
                    }
                )
                return {
                    "ok": False,
                    "reason": "unflattenable",
                    "snap": snap,
                    "remaining_qty": remaining,
                }
        return {"ok": True, "snap": snap, "reason": reason, "remaining_qty": remaining}

    def positions_snapshot(self) -> dict[str, Any]:
        return {
            t: self._pos_dict(t) for t, p in self.positions.items() if p.qty > 1e-12
        }

    def open_orders(self) -> list[dict[str, Any]]:
        return [
            self._order_snapshot(o)
            for o in self.orders.values()
            if o.state in ("submitted", "resting", "partial")
        ]

    def realized_pnl_total(self) -> float:
        return float(self.realized_pnl)

    def reconcile(self) -> dict[str, Any]:
        """Cash + inventory check from ledger events (reconstruction aid)."""
        fees = sum(float(e.get("fee") or 0) for e in self.events if e.get("event") == "order_fill")
        return {
            "cash": self.cash,
            "realized_pnl": self.realized_pnl,
            "fees_total": self.fees_total,
            "fees_from_fills": round(fees, 4),
            "fees_match": abs(fees - self.fees_total) < 1e-6,
            "n_fills": self.n_fills,
            "n_partial": self.n_partial,
            "n_no_fills": self.n_no_fills,
            "n_no_arrival_book": self.n_no_arrival_book,
            "n_unflattenable": self.n_unflattenable,
            "n_orders": len(self.orders),
            "open_positions": self.positions_snapshot(),
            "residual_qty": round(
                sum(p.qty for p in self.positions.values() if p.qty > 1e-12), 6
            ),
            "truth_label": TRUTH,
        }

    def _pos_dict(self, ticker: str) -> dict[str, Any]:
        p = self.positions.get(ticker)
        if not p:
            return {}
        return {
            "ticker": p.ticker,
            "side": p.side,
            "qty": p.qty,
            "avg_entry": p.avg_entry,
            "fees_entry": p.fees_entry,
            "realized_pnl": p.realized_pnl,
            "mfe": p.mfe,
            "mae": p.mae,
        }

    def _order_snapshot(self, so: SimOrder) -> dict[str, Any]:
        return {
            "ok": True,
            "order_id": so.order_id,
            "ticker": so.ticker,
            "side": so.side,
            "action": so.action,
            "price": so.price,
            "quantity": so.quantity,
            "tif": so.tif,
            "state": so.state,
            "filled_qty": so.filled_qty,
            "remaining_qty": so.remaining_qty,
            "avg_fill_price": so.avg_fill_price,
            "fees_paid": so.fees_paid,
            "fill_confidence": so.fill_confidence,
            "reason": so.reason,
            "latency_ms": so.latency_ms,
            "run_id": so.run_id,
            "strategy_id": so.strategy_id,
            "window_id": so.window_id,
            "truth_label": TRUTH,
            "usd": False,
        }


def replay_tape_books(
    tape_events: list[dict[str, Any]],
    *,
    sim: KalshiExecutionSim,
) -> int:
    """Feed book snapshots into sim; returns n books applied."""
    n = 0
    for ev in tape_events:
        if str(ev.get("event") or "") not in ("book_snapshot", "book_delta", "trade"):
            continue
        sim.on_book(ev)
        n += 1
    return n


__all__ = [
    "TRUTH",
    "RECEIPT",
    "LATENCY_SCENARIOS_MS",
    "KalshiExecutionSim",
    "walk_taker_buy_yes",
    "walk_taker_sell_yes",
    "parse_levels",
    "estimate_taker_fee",
    "replay_tape_books",
]
