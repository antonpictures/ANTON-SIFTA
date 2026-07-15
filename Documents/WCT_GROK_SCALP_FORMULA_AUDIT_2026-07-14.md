# WCT Grok coding order - scalp formula audit

**From:** Codex, for Alice and We Code Together  
**Date:** 2026-07-14  
**Receipt:** `r20260714-grok-scalp-formula-audit`  
**Scope:** Correct and falsify the STGM scalp laboratory. This report does not authorize, configure, or transmit USD orders.

## Verdict

Do not tune the current thresholds and do not call the current tournament leader a validated method. The laboratory contains formula, timing, state, and denominator defects that can create optimistic rankings. Correct those defects first, rerun chronologically, and let Alice select only from valid STGM evidence.

The highest-priority result is not a new predictor. It is a trustworthy matched experiment where every decision uses information available at that timestamp, entry and exit use executable prices, latency changes the arrival book, residual inventory is charged, and a complete 15-minute round is one statistical block.

## Owner-supplied live outcome evidence

George supplied a visible Kalshi history slice with 21 paid-out rows and prediction cash of `$6.70`, down from the previously observed `$10.54`.

The listed row PnLs produce:

```text
n                 = 21
wins/losses/ties  = 9 / 11 / 1
gross wins        = +$1.72
gross losses      = -$5.37
listed net        = -$3.65
average win       = +$0.1911
average loss      = -$0.4882
profit factor     = 0.3203
expectancy/row    = -$0.1738
break-even WR     = 0.4882 / (0.4882 + 0.1911) = 71.87%
cash delta        = $6.70 - $10.54 = -$3.84
unreconciled      = -$0.19 versus the visible 21-row sum
```

By asset in this small, non-independent slice:

```text
BTC  1W/5L  -$2.09
ETH  4W/3L/1T  -$0.71
SOL  2W/2L  -$0.53
XRP  2W/1L  -$0.32
YES  4W/7L/1T  -$2.56
NO   5W/4L      -$1.09
```

This is owner-supplied visible history, not yet joined to canonical order/fill receipts. Grok must reconcile the extra `-$0.19` from exchange fills, fees, omitted rows, or balance movements before using the slice as a ground-truth training table. The sample is too small and correlated for asset bans or parameter fitting, but it clearly falsifies the claim that frequent small green exits alone create a favorable payoff distribution.

## P0 defects that invalidate the current ranking

### P0.1 Cross-asset lookahead

`run_live_shadow_tournament()` builds `majors_mids` from `rows[-1]` for every asset, then passes those final values into every earlier decision. A first-tick decision can therefore receive the end-of-replay cross-asset state.

Current behavior was reproduced directly:

```text
first historical decision + future final majors -> majors_breadth = 1.0
```

**Code:** `System/alice_15m_scalp_lab.py:152-158,186`; `System/alice_15m_scalp_strategies.py:576-581`.

**Fix:** merge all asset events into one ascending `(exchange_ts_ms, recv_ts_ms, seq)` stream. At decision time `t`, construct every cross-asset feature from each asset's last event satisfying `event_ts <= t`. Never pass a replay-final map.

Define point-in-time breadth from returns, not contract price levels:

```text
r_j(t,h) = logit(mid_j(t)) - logit(mid_j(t-h))
breadth(t,h) = sum_j w_j * sign(r_j(t,h)) / sum_j w_j
```

Require at least three fresh majors and store each source timestamp. The existing formula counts `mid >= .55` as "up", which is conviction level, not movement.

### P0.2 Latency is cosmetic

The simulator computes `arrival_ts_ms = submitted_ts_ms + latency_ms`, but the lab passes the decision book as `book_at_arrival`. A 0 ms and 1,000 ms test therefore fills at the same price from the same book.

**Code:** `System/alice_15m_execution_sim.py:233-321`; `System/alice_15m_scalp_lab.py:200-214,232-245`.

**Fix:** submit an intent against a tape cursor. The simulator must select the first complete book with `event_ts >= arrival_ts_ms`; if none exists, record `no_arrival_book`. Reject stale or gap-crossing arrivals. Do not let callers inject the decision book as arrival truth except explicit unit fixtures.

### P0.3 The hold baseline is not hold-to-settlement

`HoldBaseline` says hold to settle, but the replay ends by force-selling at the last observed bid. The latest report ranks this mislabeled arm first at `+$15.0983`, despite 20 unflattenable positions. That is an end-of-tape liquidation experiment, not a binary settlement control.

**Code:** `System/alice_15m_scalp_strategies.py:302-338`; `System/alice_15m_scalp_lab.py:257-261`.

**Fix:** create two explicit controls:

```text
hold_to_settlement:
  pnl = q * (1[held_side == resolved_side] - entry_side_ask) - entry_fee

end_of_tape_liquidation:
  pnl = q * (last_executable_bid - entry_side_ask) - entry_fee - exit_fee
```

`hold_to_settlement` is eligible only when a canonical resolved outcome exists. Never substitute the last quote. Rename the current behavior and exclude incomplete windows from settlement comparisons.

### P0.4 Residual inventory disappears from strategy state

On any positive exit fill, the lab sets `st.open_qty = 0`, even if the IOC exit was partial. End-of-tape flatten also increments `n_exits` and clears state without checking whether flatten succeeded. Realized PnL can therefore be ranked while residual inventory remains in the simulator.

**Code:** `System/alice_15m_scalp_lab.py:247-261`; `System/alice_15m_execution_sim.py:423-527,601-659`.

**Fix:** after every fill, synchronize state from `sim.positions_snapshot()`:

```text
remaining = position.qty
st.open_qty = remaining
round_trip_complete = previous_qty > 0 and remaining == 0
```

Increment `n_exits` for exit orders, but increment `n_round_trips` only when inventory reaches zero. A failed/partial flatten remains open and receives a conservative liability; it is never a completed round trip.

### P0.5 The statistical denominator is wrong

The lab uses `len(by_ticker)` as `n_windows`, treating correlated assets in the same 15-minute round as independent blocks. The holdout gate sets `n_fills_proxy = n_fills + n_exits`, double-counting lifecycle events. The available `block_bootstrap_ci()` is not used by promotion.

**Code:** `System/alice_15m_scalp_lab.py:263-292,322-344,365-392`.

**Fix:** derive one canonical `round_id` from the common expiration timestamp and aggregate all asset PnL inside it:

```text
PnL_round(r) = sum_positions PnL(position in round r)
EV_round = mean_r PnL_round(r)
LCB95 = window_block_bootstrap(PnL_round).lo
```

Use unique order IDs to count submits, filled orders, partials, no-fills, and complete round trips separately. Promotion requires `LCB95 > 0`, no unresolved inventory, and a frozen chronological holdout. Do not add exits to fill counts.

### P0.6 Replay epochs overlap and are not holdouts

Every monitor tick reruns the latest tape subset, truncates each ticker to 40 observations, and writes a new epoch over substantially the same history. This is repeated overlapping backtest output, not new independent evidence.

**Code:** `System/alice_15m_scalp_lab.py:83-87,120-150`.

**Fix:** persist an immutable epoch manifest:

```text
epoch_id, policy_hash, train_round_ids, validation_round_ids,
test_round_ids, tape_hash, settlement_hash, created_ts
```

Close each round once. A round can enter one test epoch only. Do not rerank continuously on overlapping partial windows.

### P0.7 Training entries use mid, not executable ask

`open_training_scalps_for_window()` opens at `kalshi_yes` or `1-kalshi_yes` while describing a taker buy. This omits entry spread. Expiry exits are still evaluated through a quoted exit with an exit fee rather than binary settlement.

**Code:** `System/alice_15m_scalp_learner.py:786-830,925-959`.

**Fix:** define side prices once:

```text
ask_yes = yes_ask
bid_yes = yes_bid
ask_no  = 1 - yes_bid
bid_no  = 1 - yes_ask

entry(side) = ask_side
exit(side)  = bid_side
```

If an executable ask is missing, record `no_entry_quote`; do not use mid. At settlement, use the resolved 0/1 payoff and no synthetic exit trade/fee.

### P0.8 Maker logic can create unlimited resting orders

Maker intents do not update `ArmState.open_qty`, so the strategy emits another GTC order on later ticks. The ledger shows repeated resting orders for the same ticker. There is no resting-order state, cancel/replace discipline, or global order cap.

The NO maker entry is also priced from `1 - yes_bid`, which is the NO ask, so a supposed post-only order can cross. Maker exits are marked post-only while retaining an aggressive `0.01` sell limit.

**Code:** `System/alice_15m_scalp_strategies.py:266-296,466-498`; `System/alice_15m_scalp_lab.py:200-223`.

**Fix:** add `open_order_id`, `open_order_price`, `open_order_qty`, and `queue_state` to arm state. Permit one resting entry and one resting exit per ticker. Cancel or amend before replacement.

```text
post_buy_yes <= yes_bid
post_buy_no  <= no_bid = 1 - yes_ask
post_sell_side >= side_ask
```

Keep maker `fill_unknown` until real trade-through and queue data exist.

## P1 formula corrections

### P1.1 Feature names and units are misleading

Current formulas:

```text
mom_yes         = current_mid - previous_sample_mid
trend_yes       = last_mid - first_mid among last five samples
micro_vwap_yes  = arithmetic mean of those mids
```

They are sample-count dependent, ignore gaps, and `micro_vwap_yes` is neither microprice nor VWAP.

**Fix:** rename the existing field `rolling_mid_mean`. Add time-indexed returns and volatility:

```text
m_h = logit(mid_t) - logit(mid_(t-h))
sigma_h = 1.4826 * MAD(delta_logit_mid over h)
z_mom_h = m_h / max(sigma_h, sigma_floor)
microprice = (ask*bid_qty + bid*ask_qty) / (bid_qty + ask_qty)
imbalance = (bid_qty - ask_qty) / (bid_qty + ask_qty)
```

Disable depth features while quantities are synthetic. Store `feature_available=false`, not zero.

### P1.2 Entry-band gate checks the wrong object

The gate computes `cheap = min(mid, 1-mid)`. Because this is always at most `.50`, `cheap > SCALP_MAX_ENTRY (.65)` is impossible. It also does not ensure that the chosen side's executable ask is within the configured band.

**Fix:** choose the side first, derive `ask_side`, then require:

```text
SCALP_MIN_ENTRY <= ask_side <= SCALP_MAX_ENTRY
```

Record the rejected side and ask. Remove dead `MIN_SPREAD` or scope it to maker economics; taker strategies need a maximum all-in spread/slippage cost.

### P1.3 Liquidity is not measured by 24-hour volume

`volume_24h >= 500` is used as an execution gate, while the tape has one synthetic unit of depth and no trades. This cannot establish immediate fill capacity.

**Fix:** gate on observable side depth at arrival, quote age, recent trade count/notional, spread, and book continuity. Retain 24-hour volume only as a coarse cohort label.

### P1.4 Fixed thresholds ignore quantity and uncertainty

`MIN_EDGE_USD = .01/.02/.03` is an absolute ticket threshold. `SOFT_MAX_ADVERSE_USD = -.35` is also absolute. Their economics change with count, spread, volatility, and time.

**Fix:** calculate per-contract all-in costs, then scale by quantity:

```text
cost_rt_per_contract = spread_paid + fee_in/q + fee_out/q + slippage_buffer
required_move = cost_rt_per_contract + alpha_buffer(x)

alpha_buffer(x) = z95 * sigma_exit_error(x) + calibration_error(x)
```

For initial experiments keep `q=1` so strategy alpha is not confused with sizing. Later size only from a round risk budget and observed depth:

```text
q = min(q_depth, floor(R_round / max(loss_to_stop_per_contract, eps)))
```

No martingale and no increase after loss.

### P1.5 Forced 7:30 flatten is a policy hypothesis, not a truth

The training/live-style path force-flattens every open at 7:30 remaining, while the six-arm lab waits until 45 seconds. Neither cutoff is justified by a matched experiment. Forced exit may reduce binary tail risk, but it can also crystallize temporary adverse movement.

**Fix:** test a frozen cutoff grid in STGM only, with identical entries:

```text
cutoff in {600, 450, 300, 120, 45} seconds left
```

Compare fee-net PnL, CVaR, maximum adverse excursion, unflattenable rate, and scalp-minus-hold. Choose no cutoff unless its chronological holdout LCB improves. Do not force a trade or a cutoff because a previous revision named it.

### P1.6 Policy hash omits formulas and constants

The policy hash includes strategy IDs and one version string, not source content or configuration. Threshold changes can retain the same hash.

**Fix:** hash normalized strategy source plus a canonical JSON policy manifest containing all constants, feature schema version, fee model, tape schema, and exit rules.

## Correct decision formulas for the next frozen epoch

### Executable accounting

For side `s`, quantity `q`, entry ask `a_s`, future exit bid `b_s`, and outcome `Y_s`:

```text
scalp_pnl = q*(b_s - a_s) - fee(a_s,q) - fee(b_s,q)
settle_pnl = q*(Y_s - a_s) - fee(a_s,q)
```

Never use midpoint in either realized formula.

### Entry decision

Estimate a distribution, not one predicted side:

```text
EV_enter(x) = P(fill|x) * [
    sum_k P(exit_k|fill,x) * scalp_pnl_k
  + P(no_exit_then_settle|fill,x) * settle_pnl
] - no_fill_cost - tail_penalty
```

Enter only if:

```text
LCB95(EV_enter | frozen regime, strategy) > 0
```

Until enough data exist for that model, use deterministic rules as arms but keep the same complete accounting.

### Exit decision

Compare executable exit with conditional continuation:

```text
Q_exit = q*b_s - fee(b_s,q)
Q_hold = E[future liquidation or settlement value | x] - future_cost - tail_penalty
exit now iff LCB95(Q_hold - Q_exit) <= 0
```

Keep fixed TP, trailing, stop, and time-cutoff exits as separate controls. Do not combine them into one arm and then attribute performance to "scalping."

### Payoff-shape gate

For empirical win probability `p`, average win `W`, and average loss `L>0`:

```text
EV = p*W - (1-p)*L
p_break_even = L / (W + L)
```

Report uncertainty by round-block bootstrap. The owner-supplied slice has `p_break_even ~= 71.9%`; its observed non-tie win rate is `45%`. Do not optimize win rate while allowing average losses to remain much larger than wins.

## Required code order for Grok

1. **Truth patch:** remove cross-asset future leakage and make arrival-book latency real.
2. **Ledger patch:** synchronize partial fills/residual inventory; separate orders, fills, exits, and completed round trips.
3. **Control patch:** implement canonical settlement hold and rename end-of-tape liquidation.
4. **Price patch:** enter at side ask, exit at side bid, settle at 0/1 without an exit fee.
5. **Epoch patch:** chronological, non-overlapping complete rounds with immutable manifests.
6. **Statistics patch:** aggregate by common 15-minute round, use block-bootstrap LCB, and reject unresolved inventory.
7. **Maker patch:** one resting order, correct YES/NO post-only prices, cancel/replace, still shadow-only.
8. **Feature patch:** time-indexed momentum/volatility, honest availability flags, and point-in-time cross-asset breadth.
9. **Policy patch:** source/config-complete hash and frozen cutoff/exit arms.
10. **Reconciliation patch:** join George's 21 visible outcomes to exchange order/fill/fee receipts and explain the `-$0.19` difference.

## Required focused tests

Add tests that fail before the patch:

- `test_cross_asset_features_never_use_future_rows`
- `test_latency_uses_first_book_at_or_after_arrival`
- `test_gap_crossing_arrival_is_no_fill`
- `test_hold_to_settlement_uses_binary_result_not_last_bid`
- `test_partial_exit_retains_residual_position`
- `test_failed_force_flatten_is_not_completed_round_trip`
- `test_round_count_groups_correlated_assets_by_common_expiry`
- `test_holdout_fill_count_does_not_add_exits`
- `test_holdout_requires_bootstrap_lower_bound_positive`
- `test_training_entry_uses_side_ask_not_mid`
- `test_expiry_settlement_has_no_exit_fee`
- `test_no_maker_post_only_uses_no_ask_as_bid`
- `test_maker_has_at_most_one_resting_entry_per_ticker`
- `test_chosen_side_ask_obeys_entry_band`
- `test_synthetic_depth_disables_microprice_and_imbalance`
- `test_policy_hash_changes_when_formula_or_constant_changes`
- `test_zero_pnl_is_tie_not_win`
- `test_every_candidate_reject_no_fill_and_zero_trade_is_counted`
- `test_visible_history_reconciliation_accounts_for_all_cash_delta`

Resolve the two already failing tests rather than deleting them:

```text
18 passed, 2 failed

test_tick_scalps_exits_green_ticket:
  expected canonical paper position to remain; implementation now removes it

test_scalp_banks_green_early_not_only_last_five_minutes:
  expected TRAINING_OPEN_SECS_MAX == 14*60; implementation is 15*60
```

Choose and document one contract for canonical paper execution versus counterfactual shadow execution. Choose and document one entry horizon. Then update code and tests together with a new policy version.

## Acceptance criteria

Grok returns:

- exact changed files and new policy/schema versions;
- before/after reproductions for every P0 defect;
- focused test command and complete output;
- immutable epoch manifest and hashes;
- per-round PnL series including no-trades and unresolved inventory charges;
- matched hold, liquidation, fixed-exit, and dynamic-exit tables;
- owner-history reconciliation receipt;
- WCT coded receipt and stigmergic trace ID.

No arm receives a `best` label while it has future leakage, cosmetic latency, unresolved positions, missing settlement truth, or a non-positive holdout lower confidence bound. Any positive paper result remains simulator evidence and does not prove a live-money edge.
