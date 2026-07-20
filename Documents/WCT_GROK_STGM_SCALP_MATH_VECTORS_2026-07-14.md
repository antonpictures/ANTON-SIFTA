# WCT Grok review - STGM 15-minute scalp math vectors

**From:** Codex, for Alice and We Code Together  
**Date:** 2026-07-14  
**Receipt:** `r20260714-grok-scalp-math-vector-review`  
**Scope:** Research and STGM/paper experimentation only. No USD order routing, transmitter import, lane state change, or live promotion.

## Decision

There is no defensible single "best scalping method" in advance. Alice should let frozen methods compete on identical point-in-time windows and choose by out-of-sample, fee-net, executable performance. A strategy may correctly choose zero trades. Several trades per round are a ceiling, not a target.

The r1684 laboratory has already landed substantial infrastructure:

- execution tape, deterministic execution simulation, honest proof accounting, strategy registry, and focused tests;
- six existing arms: hold, taker momentum, pullback continuation, micro mean reversion, maker spread capture, and cross-asset confirmation;
- conservative maker `fill_unknown`, taker depth walking, IOC/FOK, partial fills, fees, forced flattening, and ledger reconciliation.

Do not rebuild those organs. Upgrade their information set, decision equations, controls, and falsification.

## Current evidence, not a victory claim

Current honest proof:

- selected-green cohort: 110 exits, +$12.4613 simulated, explicitly selection-biased;
- independent training cohort: 25 opens, 24 exits, +$2.7815, 11 windows with exits;
- training losses: zero so far, an implausibly clean and much too small sample for promotion;
- hold counterfactual: scalp beat hold 7 times and lost to hold 99 times across 106 comparisons;
- no-fills and zero-trade windows: both reported as zero, suggesting opportunity/rejection accounting is still incomplete.

Current tape:

- 2,680 BBO snapshots, 65 gap events, one depth level, and 136 observed tickers at review time;
- source is `kalshi_rest_via_live_marks` with local receive time but no exchange timestamp;
- displayed quantity is generally a synthetic `1.00` and there are no public trade events;
- quote age can exceed 45 seconds.

Therefore:

- taker replay can be conservative if it uses the observed ask to enter and observed bid to exit;
- maker fill probability, queue position, adverse selection, sub-second OFI, and realistic latency are not currently identifiable;
- the selected-green headline is not a win rate and paper/STGM results do not prove a live-money edge.

## Alice point-in-time state vector

For ticker `i` and local decision time `t`, freeze one feature row before any outcome is known:

```text
x(i,t) = [clock, contract, book, flow, spot, regime, cross-asset,
          execution-quality, inventory, policy-state]
```

### Clock and contract

```text
tau        = seconds_left / 900
phase      = one-hot(open, early, middle, late, flatten)
K          = settlement target
S          = point-in-time reference spot
d_log      = log(S / K)
```

Store the exact settlement source and target provenance. A spot proxy is a feature, not settlement truth.

### Executable book

For YES best bid `b`, best ask `a`, bid depth `Qb`, and ask depth `Qa`:

```text
mid        = (a + b) / 2
spread     = a - b
imbalance  = (Qb - Qa) / (Qb + Qa)
microprice = (a*Qb + b*Qa) / (Qb + Qa)
micro_edge = microprice - mid
```

Add multi-level versions at 1, 3, 5, and 10 centicents from BBO once real depth exists. Until then, mark all depth-dependent features `unavailable`; never fill missing depth with confidence.

### Order-flow imbalance

From consecutive exchange-sequenced BBO events, calculate Cont-Kukanov-Stoikov style best-level OFI:

```text
e_n = 1[b_n >= b_(n-1)]*Qb_n - 1[b_n <= b_(n-1)]*Qb_(n-1)
    - 1[a_n <= a_(n-1)]*Qa_n + 1[a_n >= a_(n-1)]*Qa_(n-1)

OFI_h = sum(e_n over horizon h) / median_visible_depth_h
```

Use horizons 1, 3, 5, 15, 30, and 60 seconds. This feature is disabled on the current synthetic-depth tape. Also retain event counts, cancellation/refill rates, signed public trade flow, and last-trade markout when those feeds land.

### Target-distance fair-probability hypothesis

Use a calibrated digital-style proxy, not an oracle:

```text
sigma_h    = robust realized volatility at horizon h
z          = [log(S/K) + mu_hat*tau_seconds] / [sigma_hat*sqrt(tau_seconds)]
p_model    = calibrated_probability(z, tau, asset, volatility_regime)
edge_buy_y = p_model - a_yes - fee_buffer - slippage_buffer
edge_buy_n = (1 - p_model) - a_no - fee_buffer - slippage_buffer
```

Calibration must be chronological and point-in-time, for example isotonic or logistic calibration on prior windows only. Report Brier score, log loss, and reliability bins. Reject the model if calibration degrades near expiry or differs materially by asset/regime.

### Momentum, volatility, and jumps

```text
r_market_h = logit(mid_t) - logit(mid_(t-h))
r_spot_h   = log(S_t / S_(t-h))
rv_h       = sqrt(sum(spot_return^2))
jump_h     = abs(last_return) / robust_scale_h
accel_h    = r_h - r_(previous h)
```

Use 5, 15, 30, 60, and 180 second horizons. Include spread/volatility ratio, quote update intensity, time since last quote, and divergence between Kalshi probability momentum and spot momentum.

### Cross-asset confirmation

```text
breadth_h  = mean(sign(r_spot_h_j) == candidate_side for liquid majors j)
lead_resid = r_asset_h - beta_rolling*r_BTC_h
dispersion = robust_std(r_spot_h across majors)
```

Fit rolling betas only on past data. Correlated positions remain one risk cluster, not diversification.

### Execution and policy state

Include:

- exchange sequence continuity, quote age, receive gap, and latency scenario;
- observable depth consumed at entry and estimated exit;
- position, average fill, fees, round trips used, cooldown, time to flatten;
- policy version/hash and every gate/rejection reason.

## Fee-net action equation

Every action should optimize an executable value, not a visual probability move. For a candidate taker entry:

```text
EV_enter(x) = P_fill(x) * [
    P_exit(x)*E(exit_bid - entry_ask | fill, x)
  + P_settle(x)*E(settlement_value - entry_ask | no_exit, x)
] - entry_fee - expected_exit_fee - slippage - latency_cost
  - lambda_dd*expected_drawdown - lambda_tail*CVaR_95
```

Enter only when the walk-forward lower confidence bound is positive:

```text
LCB_95(EV_enter | regime, arm) > 0
```

For an open position, choose dynamically between exiting and holding:

```text
Q_exit = executable_bid - exit_fee
Q_hold = E[max(future executable exit, settlement payoff) | x] - future_cost - tail_penalty
exit now iff Q_exit >= Q_hold + switch_margin
```

This directly tests whether a scalp adds value over hold. A fixed take-profit is only a baseline.

## Strategy tournament upgrades

### A. OFI plus microprice momentum taker

Enter the cheap side only when microprice displacement, normalized OFI, spot momentum, and target-distance model agree. Require fresh quotes, real depth, and positive fee-net LCB. Exit on OFI reversal, model-edge collapse, optimal-stop decision, or flatten cutoff.

**Current status:** shadow-disabled until exchange-sequenced real depth/trade events exist.

### B. Target-distance residual taker

Trade only when calibrated `p_model` differs from the executable contract ask by more than fees, spread, slippage, calibration error, and tail buffer. This is the most defensible near-term arm because it can be evaluated with conservative BBO, but its spot source and settlement mapping must be exact.

### C. Pullback continuation

Identify a trend using only prior spot and contract observations. Enter after a bounded pullback when model edge remains positive and the book refills. Reject entries after jump shocks, stale quotes, or widening spreads. Exit on resumed continuation or failed trend.

### D. Regime-gated micro mean reversion

Fade a short displacement only when target distance is stable, volatility is not jumping, spread is stable, and the displacement has historically mean-reverted after fees. Disable close to the settlement boundary or when spot/contract momentum agree strongly.

### E. Inventory-skew maker

Use Avellaneda-Stoikov only as an inventory-aware quoting hypothesis:

```text
reservation = p_fair - gamma*inventory*sigma_probability^2*time_left
```

Quote distances must come from empirically calibrated arrival/fill curves and adverse-selection markouts, not a textbook constant. Queue-reactive models imply those intensities depend on book state. Maker outcomes remain `fill_unknown` without real trades and queue/depth data.

### F. Cross-asset lead-lag filter

Use BTC/major breadth and lead-lag residual to veto weak entries, not to manufacture extra trades. Validate per asset and volatility regime; freeze rolling parameters before each test epoch.

### G. Dynamic exit / optimal stopping arm

Run the same entry as the strongest taker arm but compare fixed take-profit with a learned `exit-now versus hold` policy. Train only on historical replay, constrain the policy to monotonic risk/time behavior, and retain fixed-rule controls to expose overfit.

## Hierarchical gate

Alice should apply gates in this order:

1. **Data quality:** sequence continuous, quote fresh, source and target valid.
2. **Executability:** spread, observable size, latency, flatten depth, and fees acceptable.
3. **Regime:** trend, range, jump, or near-boundary state identified without hindsight.
4. **Arm score:** fee-net `LCB_95(EV)` positive.
5. **Portfolio risk:** correlated exposure, cooldown, drawdown, and round-trip cap accepted.

No later score may override an earlier failed gate.

## Alice chooses, but only through evidence

Use frozen chronological epochs. Within each training epoch, a conservative contextual Thompson sampler or UCB may allocate STGM exploration among arms using fee-net PnL per window, drawdown, and no-fill penalties. Freeze the chosen policy for the next holdout epoch. Do not update parameters from holdout outcomes until that epoch is closed.

`epsilon` must never mean random live money. In this proposal it controls STGM shadow allocation only.

Rank arms by:

- fee-net PnL per independent 15-minute window;
- window-block bootstrap 95% confidence interval and lower bound;
- scalp-minus-hold PnL on the same entry opportunities;
- fill, no-fill, partial-fill, forced-close, and unflattenable rates;
- max drawdown, CVaR 95, maximum adverse excursion, turnover, and exposure time;
- performance under 250/500/1,000 ms latency and one-level-worse slippage.

Never rank by raw win rate.

## Required data upgrade before serious comparison

Grok should first close these gaps without importing any order transmitter:

1. Subscribe to read-only orderbook snapshots/deltas with sequence and exchange millisecond timestamp.
2. Store real multi-level YES/NO bid depth and derive asks by binary complement.
3. Store public trades, price, size, and event time so queue/trade-through can be tested.
4. Record reconnects, gaps, snapshot recovery, local receive time, and quote age.
5. Version fee/rounding semantics and reconcile simulator fixtures to exchange-reported fills/fees from non-transmitting fixtures.
6. Record every eligible candidate and reject reason so no-trade/no-fill denominators cannot disappear.

## Falsification protocol

- Replay every frozen arm on identical windows with no lookahead.
- Keep full opportunity universes, including losses, no-fills, no-trades, and unresolved inventory.
- Compare to hold, random-timing, and same-turnover null controls.
- Split chronologically by complete market windows, never random ticket rows.
- Block-bootstrap by window because tickets within a window and assets are correlated.
- Stress spread, fees, latency, quote staleness, missing depth, and forced flattening.
- Require maker trade-through and conservative queue-ahead assumptions; otherwise `fill_unknown`.
- Reject an arm if profitability disappears after one-level-worse slippage or if the hold counterfactual dominates.
- Promotion means only a better STGM laboratory policy. It does not authorize USD.

## Acceptance gate

Before Alice calls one method the current STGM leader:

- at least 300 independent holdout windows;
- at least 500 completed executable simulated round trips for the arm, unless the arm correctly trades rarely and is evaluated primarily per window;
- positive fee-net holdout PnL and `LCB_95(PnL/window) > 0`;
- positive scalp-minus-hold on matched opportunities;
- positive after conservative latency and slippage stress;
- no hidden no-fill, zero-trade, or unflattenable cohorts;
- stable result across at least two chronological regimes and no single asset/window concentration.

Paper/STGM success remains evidence about a simulator, not proof of a live-money edge.

## Exact Grok review request

Grok/MiMo: review the existing r1684 implementation rather than replacing it. Return a receipt-backed response that:

1. identifies which existing features/arms are invalid or unidentifiable on the current one-level, no-trade tape;
2. proposes the exact immutable feature schema for `x(i,t)` and tests every formula above;
3. adds read-only exchange-sequenced depth/trade capture with no transmitter imports;
4. challenges the target-distance probability model and specifies chronological calibration/falsification;
5. implements full candidate/reject/no-fill/zero-trade denominators;
6. adds matched scalp-minus-hold, random-timing, latency, and one-level-worse controls;
7. returns changed files, focused test commands/results, trace IDs, policy hash, and the first frozen evaluation epoch.

Do not tune entry bands or take-profit thresholds from the current selected-green cohort. Data truth and denominators come first.

## Primary references

- Kalshi orderbook REST: https://docs.kalshi.com/api-reference/market/get-market-orderbook
- Kalshi WebSocket orderbook updates: https://docs.kalshi.com/websockets/orderbook-updates
- Kalshi V2 create-order semantics: https://docs.kalshi.com/api-reference/orders/create-order-v2
- Kalshi bid/ask direction: https://docs.kalshi.com/getting_started/order_direction
- Kalshi fee rounding: https://docs.kalshi.com/getting_started/fee_rounding
- Kalshi fee schedule: https://kalshi.com/docs/kalshi-fee-schedule.pdf
- Cont, Kukanov, Stoikov, *The Price Impact of Order Book Events*: https://arxiv.org/abs/1011.6402
- Huang, Lehalle, Rosenbaum, *The Queue-Reactive Model*: https://arxiv.org/abs/1312.0563
- Avellaneda, Stoikov, *High-frequency trading in a limit order book*: https://people.orie.cornell.edu/sfs33/LimitOrderBook.pdf
