# WCT Plan r1684 - STGM 15-minute intrawindow scalping laboratory

**From:** Codex, for Alice and We Code Together  
**Date:** 2026-07-14  
**Owner direction:** Build a subset of algorithms that can buy and sell several times inside one Kalshi 15-minute window, but execute them in STGM/paper with the same market and order semantics a USD API path would face.  
**Receipt:** `r1684-stgm-intrawindow-scalp-lab-plan`

## Scope and hard boundary

This plan is for an execution-realistic STGM laboratory. It does not place, route, sign, or enable real-USD orders. It may read public market data and compare its simulated order schema with Kalshi's documented V2 schema. Any future live-money decision is a separate owner-controlled project and is not an output of this plan.

The goal is not to force several trades per window. The goal is to let several algorithms compete for zero to three complete round trips per ticker/window, and to count no-trade as correct when fees, spread, depth, or remaining time remove the edge.

## What Alice already has

### Market observations

- `.sifta_state/kalshi_15m_live.jsonl` contains 15,480 snapshots from roughly 2026-07-11 through 2026-07-14, usually around the monitor's 15-second cadence.
- Each historical row covers the nine-asset 15-minute strip and includes ticker, asset, current implied price, seconds remaining, target, and direction display values.
- The current `.sifta_state/kalshi_15m_live.json` snapshot additionally exposes top-of-book `yes_bid` / `yes_ask` and 24-hour volume.
- Coinbase proxy spot features already include short returns, volatility, trend, range position, volume ratio, and a point-in-time predicted side. These are context features, not settlement truth.
- A manual Kalshi Pro tape receipt records examples of actual spread, displayed size, 5-minute volume, and the difference between a liquid BTC clock and dead/dust books.

### Existing scalp machinery

- `System/alice_15m_scalp_learner.py` already calculates a conservative side exit from the bid, estimates entry and exit fees, requires a minimum fee-net edge, and compares virtual scalp exits with hold-to-settlement.
- The paper monitor calls both `tick_training_scalps()` and `tick_scalps()` every 15 seconds.
- Training can open up to three STGM-only tickets per 15-minute window on liquid, non-weird majors.
- The current simulator has a minimum hold time, liquidity floor, time-to-close gates, fee-net take-profit threshold, and an expiry close path.
- The production client contains an inert reduce-only cash-out shape that documents how a close would map to a V2 order without transmitting it.
- Existing tests cover fee arithmetic, bid-side exits, no-early-harvest behavior, per-window idempotency, and scalp-versus-hold grading.

### Current evidence, interpreted honestly

- Scalp log: 2,129 rows total.
- Shadow exits: 91 rows across 89 unique tickers.
- Independent multi-ticket training: only 8 opens and 8 exits.
- Hold comparisons: 87; scalp beat hold 4 times and lost to hold 83 times.
- The proof file reports 99/99 profitable scalp exits and +$12.9138 simulated fee-net PnL, but this is selection-biased: the current algorithm records an exit only after it observes a fee-net green quote. It is not a full opportunity sample and cannot be read as a 100% winning strategy.
- The training book marked most windows as opened with zero eligible tickets. This is useful negative evidence, but the summary currently hides the reason distribution.
- Current paper proof remains negative in unit PnL. A high win rate or a positive selected-exit ledger is not proof of an executable edge.

## What data is missing

### P0 missing execution tape

The historical tape does not retain:

- bid and ask at each timestamp;
- full orderbook levels and available quantity;
- public trades, aggressor side, and trade size;
- 1-minute / 5-minute rolling volume at decision time;
- exchange sequence number and millisecond exchange timestamp;
- local receive timestamp and source latency;
- quote age, gaps, reconnects, and dropped deltas;
- spread changes and depth consumed between decision and simulated arrival.

Without these fields, entry at mid and exit at a later bid is optimistic and fill probability cannot be measured.

### P0 missing order lifecycle truth

The simulator does not yet model:

- submit, acknowledge, partial fill, remaining quantity, cancel, amend, and expiry;
- IOC versus FOK versus resting GTC behavior;
- maker queue position and adverse selection;
- self-trade prevention;
- multi-level slippage for size beyond top-of-book;
- exact per-fill fees, fee accumulator, balance rounding, and rebates;
- no-fill and late-cancel outcomes;
- inventory after each partial fill;
- a complete sequence of multiple round trips in the same ticker/window.

### P1 missing scientific controls

- No preregistered opportunity universe: green-only exits dominate the proof.
- No frozen train/validation/test split by time and window.
- No latency stress test.
- No fill-model calibration against observed trades.
- No per-algorithm drawdown, turnover, exposure time, adverse excursion, or capacity report.
- No reason ledger for every rejected candidate and every zero-trade window.
- No block confidence interval by 15-minute window; tickets in the same window are correlated.

## Official Kalshi semantics the simulator must mirror

Use the current official documentation as the contract, version-stamped in every run:

- Orderbook REST returns active YES and NO bids; derive the opposite asks from binary complement pricing.
- The V2 orderbook supports fixed-point price and quantity and depth queries.
- V2 orders use one YES-price scale with `bid` / `ask`, explicit count, price, time-in-force, self-trade prevention, post-only, and reduce-only fields.
- Create-order responses expose immediate fill count, remaining count, average fill price, and average fee paid.
- WebSocket orderbook snapshots/deltas provide sequence and millisecond timestamps; use `use_yes_price: true` so both sides share one scale.
- Fee and rounding behavior must be versioned from the current fee schedule and reconciled against `average_fee_paid`; do not trust a permanently hard-coded formula.

References:

- https://docs.kalshi.com/api-reference/market/get-market-orderbook
- https://docs.kalshi.com/websockets/orderbook-updates
- https://docs.kalshi.com/api-reference/orders/create-order-v2
- https://docs.kalshi.com/getting_started/order_direction
- https://docs.kalshi.com/getting_started/fee_rounding
- https://kalshi.com/docs/kalshi-fee-schedule.pdf

## Proposed architecture

Extend the existing scalp organ; do not fork a second prediction picker.

### 1. Execution-grade read-only tape

Proposed module: `System/alice_15m_execution_tape.py`

Write append-only events to `.sifta_state/alice_15m_execution_tape.jsonl`:

```json
{
  "event": "book_snapshot|book_delta|trade|gap|reconnect",
  "ticker": "KXBTC15M-...",
  "window_id": "...",
  "exchange_ts_ms": 0,
  "recv_ts_ms": 0,
  "seq": 0,
  "yes_bids": [["0.5600", "12.00"]],
  "no_bids": [["0.4300", "8.00"]],
  "trade_price": null,
  "trade_size": null,
  "seconds_left": 0,
  "source": "kalshi_rest|kalshi_ws",
  "truth_label": "ALICE_15M_EXECUTION_TAPE_V1"
}
```

Start with rate-limited batch REST orderbook snapshots for all active 15-minute tickers. Add authenticated read-only WebSocket snapshots/deltas only when continuity, sequence-gap recovery, and secret handling are tested. The tape writer never imports an order transmitter.

### 2. Deterministic Kalshi execution simulator

Proposed module: `System/alice_15m_execution_sim.py`

One interface for all strategies:

```text
submit(order) -> simulated order id
on_book(event) -> fills / partial fills / no fill
cancel(order_id)
amend(order_id, price, quantity)
positions() / realized_pnl() / open_orders()
```

Rules:

- Taker orders walk observable depth at the simulated arrival timestamp.
- Maker fills require observable later trade flow through the level and a conservative queue-ahead model. If queue cannot be estimated, mark the result `fill_unknown`, not filled.
- Run every decision through latency scenarios such as 250 ms, 500 ms, 1 s, and the observed p95 receive gap.
- Apply fees per fill from a versioned fee model and also retain exchange-reported fee fixtures.
- Derive cash, inventory, realized PnL, unrealized PnL, fees, and rounding from ledger events, never mutable counters alone.
- Force all open simulated inventory to a conservative executable bid before the market cutoff; report liquidation failure if depth is absent.

### 3. Strategy subset tournament

Proposed module: `System/alice_15m_scalp_strategies.py`

All arms receive the identical point-in-time tape and may produce zero to three round trips per ticker/window.

1. `hold_baseline`: existing one-entry hold-to-settle control.
2. `taker_momentum_tp`: enter only after direction, spread, depth, and short-horizon momentum confirm; exit at fee-net target, trailing reversal, or time stop.
3. `pullback_continuation`: in a confirmed direction, wait for a bounded pullback toward micro-VWAP, then exit on continuation; no averaging down.
4. `micro_mean_reversion`: fade only a preregistered short-lived price displacement with stable target distance and two-sided depth; independent from Alice's settlement-direction fade learner.
5. `maker_spread_capture`: post-only entry/exit around fair value, but remain shadow-only until queue and adverse-selection calibration are credible.
6. `cross_asset_confirmation`: use BTC/ETH/SOL field breadth only as an entry filter for one asset; never count correlated positions as diversification.

Shared limits for the laboratory:

- STGM/paper only.
- Liquid majors first: BTC, ETH, SOL, XRP, BNB. Weird/dust assets remain separate shadow cohorts.
- Maximum three open simulated positions across the window.
- Maximum three completed round trips per ticker/window.
- No martingale, no averaging down, no forced trade quota.
- Cooldown after a stop or failed exit.
- Hard no-new-entry cutoff and conservative flatten cutoff before expiry.
- A strategy that cannot flatten at an observable bid records a loss/unknown, never an imaginary exit.

### 4. Immutable event ledger

Proposed ledger: `.sifta_state/alice_15m_scalp_orders.jsonl`

Every row includes:

- run id, strategy id/version, policy hash, window id, ticker, asset;
- decision timestamp and complete feature snapshot hash;
- order intent, arrival timestamp, side, price, quantity, TIF;
- state transition: submitted, resting, partial, filled, canceled, expired, rejected;
- fill price/size, queue assumption, slippage, fee, rounding, latency scenario;
- position before/after, realized PnL, maximum favorable/adverse excursion;
- explicit reason for every no-trade and no-fill.

The proof report must be reconstructable from this ledger.

## Work phases and acceptance tests

### Phase A - Fix evidence accounting

- Split selected green exits from independent training round trips.
- Recompute proof from unique order/position lifecycle events.
- Add `n_opportunities`, `n_entries`, `n_fills`, `n_no_fills`, `n_round_trips`, `n_forced_closes`, and `n_zero_trade_windows`.
- Preserve the old proof as legacy evidence; do not rewrite history.

Acceptance: the current 99/99 headline is no longer presented as an unbiased win rate. Tests prove duplicate tickers and repeat ticks cannot inflate counts.

### Phase B - Capture qualified tape

- Store BBO and depth for every active market at sub-15-second cadence within API limits.
- Record gaps and quote age.
- Derive 1-minute and 5-minute volume from point-in-time trades, not 24-hour totals.

Acceptance: at least 100 complete windows with greater than 99% expected sample coverage, no silent sequence gaps, and replay reproduces the same BBO stream.

### Phase C - Execution simulator

- Implement taker depth walking, maker queue scenarios, partial fills, cancels, amend, fees, rounding, and latency stress.
- Replay official and local fixtures.

Acceptance: deterministic replay; cash plus inventory reconciles on every event; impossible fills are rejected; all open inventory is resolved or explicitly marked unflattenable.

### Phase D - Algorithm tournament

- Freeze strategy versions before each epoch.
- Run every arm on the same windows and latency scenarios.
- Report fee-net EV/round trip, EV/window, fill rate, turnover, exposure time, max drawdown, p95 loss, adverse excursion, scalp-minus-hold, and zero-trade frequency.

Acceptance: no arm is ranked by raw win rate. Confidence intervals are block-bootstrapped by window.

### Phase E - Out-of-sample gate

- Minimum 300 independent 15-minute windows and 500 filled round trips per candidate arm.
- Positive fee-net EV on a chronological holdout.
- Window-block 95% lower confidence bound above zero.
- Positive result under conservative latency and one-level-worse slippage stress.
- Drawdown and unflattenable-position rates within preregistered bounds.

Passing this gate means only "promote within the STGM laboratory." It does not authorize live USD.

### Phase F - Glass and owner report

Show, per active simulated position:

- strategy, entry fill, current executable exit, spread/depth, fees paid/estimated, fee-net PnL;
- order state and fill confidence;
- seconds left, exit target, stop/time cutoff;
- round trips this window and remaining cap;
- hold counterfactual and reason for no-trade/no-fill.

The owner summary must distinguish realized scalp PnL, open mark, hypothetical hold PnL, and final settlement PnL.

## Test matrix

- Bid/ask complement math for YES and NO.
- Multi-level taker fills and insufficient depth.
- Partial fill then cancel; cancel race after fill.
- Maker queue ahead, trade-through, adverse selection, and never-filled order.
- Exact fee and centicent/balance rounding fixtures.
- Sequence gap and reconnect snapshot recovery.
- No lookahead under replay.
- Multiple round trips with inventory never flipping accidentally.
- Forced flatten with and without executable depth.
- Duplicate event idempotency and crash recovery.
- Same-window correlation and block-bootstrap reporting.
- UI totals equal event-ledger totals.

## We Code Together assignments

1. **Grok/MiMo review:** challenge the orderbook, queue, fee, and latency assumptions; propose schemas/tests before coding.
2. **Codex implementation review:** protect ledger reconstruction, deterministic replay, and no-lookahead invariants.
3. **Alice paper organ:** continue current STGM loop while the new laboratory runs as an isolated shadow cohort.
4. **George review:** judge whether the glass explains each buy, sell, no-fill, and loss without requiring code knowledge.

## Expected receipts

- `r1684-a-scalp-proof-accounting`
- `r1684-b-execution-tape`
- `r1684-c-kalshi-execution-sim`
- `r1684-d-scalp-strategy-tournament`
- `r1684-e-scalp-holdout-gate`
- `r1684-f-scalp-glass`

Each receipt must include files, tests, replay interval, data coverage, strategy version, policy hash, and a statement that no USD order path was called.

## Definition of done

Alice can replay a complete 15-minute window, allow several algorithms to submit realistic STGM orders, simulate fills and exits against point-in-time executable liquidity, perform up to a few honest round trips when opportunities exist, and reconstruct every cent-equivalent of fee-net PnL from the event ledger. Losing and zero-trade windows remain in the evidence. No claim of edge is made until the chronological holdout gate passes.

