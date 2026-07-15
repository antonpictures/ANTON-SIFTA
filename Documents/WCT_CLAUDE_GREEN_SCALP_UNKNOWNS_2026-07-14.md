# WCT — Claude answers Alice's green-scalp unknowns
receipt: r20260714-wct-green-scalp-unknowns-claude · doctor: cowork_claude (claude-fable-5) · 2026-07-14

Legend: ✅ = verified on disk this session · ⚠️ = inferred from code structure, needs a probe · ❓ = unknown, measurement required.

## A. Dual-lane parity — THE headline

**A1 (✅ verified, this is the big one):** There is **no shared decision function**. The fork:
- STGM/paper: `System/alice_15m_scalp_strategies.py` — `regime_gate` (line 151), `salvage_exit_should_fire` (314), `salvage_exit_intent` (346), wired into the exit stack at line 418–419 and into `System/alice_15m_scalp_lab.py:374`.
- US$: `System/alice_usd_must_scalp.py` — `tick_must_scalp` (line 250) is a **separate path**. `grep` finds ZERO references to `regime_gate` or `salvage` in `alice_usd_must_scalp.py`, `kalshi_usd_hand.py`, `kalshi_usd_lane.py`, `kalshi_usd_audit.py`.
- **Desync risk is not hypothetical — it is the current state.** Paper learns with gates the money hand doesn't have. Any paper stats are unrepresentative of what US$ would do until parity lands.

**A2 (❓):** Lag path not instrumented end-to-end. `kalshi_usd_hand.py` has no `decision_ts`/`arrival`/`rtt` stamps (grep empty). Needs the lag harness (coding order #1 below) before anyone claims book-at-arrival vs decision-time.

**A3 (✅ partial):** US$ attempts do log: `_log` (must_scalp:48) and `_write_sit(reason, detail)` (must_scalp:59) stamp sit/skip rows; `kill_switch_active` rejects return `{"ok": False, "reason": "kill_switch"}` (kalshi_usd_hand.py:270). ⚠️ Whether the full denominator candidate→reject→submit→partial→fill is one joinable stream is unverified — likely scattered across ledgers. Harness must unify it.

**A4 (✅):** Skip reasons are stamped via `_write_sit` on the US$ side. ❓ The reverse direction (STGM skipped, US$ didn't) has no stamp because the lanes don't share a decision point — see A1.

**A5 (⚠️):** Paper fee = `estimate_taker_fee` (`alice_15m_scalp_learner`, re-exported via `alice_15m_execution_sim.py:44`). Live-vs-paper fee delta on real fills: ❓ not measured. The $0.19 unreconciled from the Grok audit says the delta is nonzero. Harness metric.

**A6 (recommendation, $20.44 book):** night_loss **−$3.00** hard halt (≈15% of bank); cooldown after force-flat red: **2 windows** (the `_force_flat_red_cooldown` scaffold at must_scalp:161 already exists ✅); max **4 tickets/hour**. One bag, $1 (see F31).

## B. Green-scalp payoff math

**B7 (✅ doctrine already on glass):** selected_green_exit is selection-biased — the app banner says so itself. True per-started-ticket EV: ❓ blocked on the Grok audit P0 repairs (r20260714-grok-scalp-formula-audit, queued). Do not trust any EV that ignores no-trades and unresolved inventory.

**B8:** Last audit: avg win +0.1911 / avg loss −0.4882, PF 0.32 (✅ from audit row). Post-salvage sim target: loss tail should compress toward **−0.25 to −0.30** (salvage banks the 20–40¢ residual on dead tickets). Measure, don't assume.

**B9:** Break-even WR: green-only needed ~72%. With salvage cutting dead tickets at ~25–35¢ residual, BE_WR falls to roughly **60–64%** (avg loss ≈ −0.30 vs win +0.19). She pays 65% now — salvage is what turns "close" into "green". Confirm on tape.

**B10 (❓):** Entry clock — no evidence yet. The tape file exists (`alice_15m_execution_tape.py`); harness should bucket fills by minute-in-window and spread. No taste-based answer.

**B11 (❓):** Per-asset fee-net LCB not computed post-audit. Note HYPE/ZEC already banned (r1669). Keep asset weights OUT until epoch manifest exists (E26).

**B12:** Matched hold-vs-scalp counterfactual is exactly what `settle_position_binary`/`aggregate_round_pnl` from the Grok audit deliver. Answer after P0s land, not before.

## C. Regime + salvage holes

**C13 (✅):** `regime_gate` is in strategies + lab paper loop ONLY. US$ hooks missing. Exact hook: inside `tick_must_scalp` (must_scalp:250) before ticket creation, same call shape as `alice_15m_scalp_lab.py:374`.
**C14 (✅):** Same — salvage is in strategy `_exit_if_open` stack (strategies:418) only. US$ hook: the hand's take-profit/exit tick in `kalshi_usd_hand.py` session loop.
**C15 (❓):** No sensitivity sweep run. Harness todo: grid {0.25, 0.30, 0.35} × {60s, 90s, 120s} on replayed tape. Config keys exist (thresholds not hardcoded ✅).
**C16 (❓):** Snap-back rate unmeasured. Guard already partial: salvage requires quoted bid > 0 and >90s; add "two consecutive red quotes" debounce if tape shows >20% snap-back.
**C17 (✅ by construction):** No dead zone: regime gate blocks NEW entry; salvage acts on OPEN tickets. A ticket entered before the field flipped is exactly the salvage case. No double-count — different lifecycle stages.

## D. Execution quality

**D18 (⚠️):** Candidates: `swarm_kalshi_public_feed.py` (public), `kalshi_prod_trade_client.py` (authenticated), Safari glass. Decision truth must be the **authenticated API book at arrival** — glass is display only. Verify in harness.
**D19 (❓):** RTT p50/p95 never measured on this machine. Harness metric #1.
**D20 (❓):** Min depth for IOC fill — paper assumes fill (audit P0). Harness: log book depth at submit, compare fill ratio.
**D21 (⚠️):** Residual tracking on US$: the audit found the paper lab vanished residuals; US$ side unverified. Harness must assert position=0 after force-flat or track residual explicitly.
**D22 (✅ from audit constraints):** Taker-only for scalps; maker remains shadow-only until trade-through + queue evidence.

## E. Lab honesty

**E23 (✅):** Grok audit row still `proposal_queued` — LCB>0, no-lookahead, latency book, residual sync **all still block promotion**. Glass shows promote NO, EV −0.046. Honest.
**E24/E25 (❓):** n_rounds vs n_tickers and training-ask-vs-mid bias: named in the audit, unrepaired until that row is coded.
**E26:** ONE frozen epoch manifest (immutable, non-overlapping — audit deliverable) is the only thing allowed to change US$ params. Nothing tuned from live glass.

## F. The stacks (config, priority order)

**F27 Exit stack (per open ticket, evaluated top-down every odds refresh):**
1. fee-true green TP (existing selected-green, now honest cohort)
2. salvage red-field: side_imp ≤ 0.30 AND >90s left AND quoted bid>0 → exit at bid
3. soft adverse: side_imp ≤ 0.42 AND <180s left AND bid ≥ entry−15¢ → exit (cap the mid-tail)
4. force-flat at ≤7:30 clock (existing force-flat 34 rule)
All thresholds in config: `green_tp`, `salvage_imp=0.30`, `salvage_min_s=90`, `soft_imp=0.42`, `soft_max_s=180`, `soft_max_loss_c=15`.

**F28 Entry stack (evaluated top-down; ANY fail → SIT, sit is the default):**
1. regime align (gate, 0.70)
2. price band 40–65¢ (existing deal)
3. co-dir field agrees
4. rainman floor ≥ 0.55
5. spread ≤ 4¢ AND depth ≥ 3× bag at ask
No forced quota. Empty window = valid outcome.

**F29 Targets for next 20 dual-shadow tickets:** fee-net sum > $0; max DD ≤ $2.50; salvage rate 15–35% (below 15% = threshold too tight, above 35% = entries bad); force-flat red ≤ 2/20; STGM−US$ shadow fill gap ≤ 3¢ median.

**F30 Kill criteria (auto-HALT via existing `set_kill_switch`, kalshi_usd_hand.py:1209 halt path ✅):** 2 force-flat reds in 45m; OR day fee-net < −$3.00; OR fill-gap median > 5¢ over 10 tickets; OR any unreconciled cash > $0.25.

**F31 With $20.44: (c) shadow-only until the lag suite is green, THEN (b) one bag $1.** Reason: A1 — the money hand doesn't even have the gates yet; arming now buys data paper already gives free. $2 bags = 10% of bank per ticket = ruin math on a 65% payer.

## G. Deliverables

**G2 Gap list — STGM has / US$ missing:**
| STGM has (✅ on disk) | US$ missing |
|---|---|
| regime_gate (strategies:151, lab:374) | no call anywhere in usd path |
| salvage exit (strategies:314/346/418) | no call anywhere in usd path |
| honest WHY cohorts | ⚠️ unverified on usd ledger |
| fee model estimate_taker_fee | live-fee delta unmeasured |
| force-flat + cooldown scaffold (shared concept) | lag/RTT stamps absent |

**G3 WCT coding order:**
- **P0 r20260714-usd-parity-gates:** wire `regime_gate` + salvage/soft-adverse exit stack into `tick_must_scalp` + hand exit tick, importing THE SAME functions from `alice_15m_scalp_strategies` (no copy-paste fork). Tests: replay BNB-98% case through the usd decision path.
- **P0 r20260714-dual-lag-harness:** stamp decision_ts, submit_ts, ack_ts, book-at-decision, book-at-arrival on every usd attempt (shadow mode); emit one joinable stream candidate→sit/reject→submit→partial→fill→exit-reason. 20-ticket shadow report with F29 metrics.
- **P1:** salvage sensitivity grid on tape (C15/C16); per-asset fee-net LCB (B11); entry-clock evidence (B10).
- (already queued) grok formula audit P0s remain the promotion blocker — do not reorder past them.

**G4 No-code owner checklist before "US $ LANE ON":**
1. Parity row coded + tests green (usd path calls the same gate/salvage functions).
2. 20 dual-shadow tickets hit F29 targets — printed, not narrated.
3. Kill criteria F30 armed and test-fired once (halt + un-halt receipt).
4. Frozen epoch manifest exists; params hash-pinned to it.
5. Night loss −$3.00 set; one bag $1; max 4 tickets/hour.

**G5 What NOT to optimize:** win-rate vanity (65% payer already — PF is the deficit); forced ticket quotas (18/window spraying); multi-bag on $20; new predictors before measurement; maker path; ANY threshold retuning from live glass instead of frozen epoch.

**Constraint honored:** nothing here transmits USD. Green = fee-true residual > 0 at a quoted price, never mid mark.

For the Swarm. 🐜⚡
