# WCT Plan r1629 — Grok: dollar-parity STGM, backtest harness, Rainman epoch

**From:** Cowork Claude (claude-fable-5) · **For:** Grok (We Code Together)
**Date:** 2026-07-12 · **Context:** r1628 P0/P1/P2/P5 shipped and verified by
owner report (glass-only app, settle backoff, seek-tails, launchd). Codex is
out of credits; Grok carries the coding load. Owner directive: keep improving
Stigmergic Predictions.
**Receipt of this plan:** `r1629-grok-predictions-plan`

Grok, Step 0: `write_plan(...)` before cutting. Order: A → B → C → D → E.

## Standing rules (frozen, same as r1628)

Kalshi USD **OFF** · prove rule untouched (pnl>0 · ≥30 settled · WR≥55%, and
proven only ends the freeze — George decides) · entry gate 0.70–0.88 ·
fade caged · one writer (launchd monitor) · §4.1 receipts per cut · backtest
before any live knob.

## A — Dollar-parity body stakes (owner ask: "0.0005 → 0.0010, match one dollar")

Goal: George reads the STGM column as dollars÷1000 with zero head-math.

1. Stake per ticket: **0.0005 → 0.0010 STGM**, meaning `0.0010 STGM ≡ $1`.
2. **Mirror the dollar economics** (this is the point, not just the digit):
   - win → `+0.0010 × (mult_net − 1)` (e.g. 74¢ win ⇒ +0.00035 STGM ≈ +$0.35)
   - loss → `−0.0010` (≈ −$1)
   The symmetric ±stake game is retired; her body now feels the same
   favorite-payoff asymmetry as real dollars — the training wheels match the
   bike before she ever rides it.
3. Rescale every floor/cap/halt proportionally (current safety cap 0.0100 was
   20 symmetric tickets; recompute for asymmetric payouts and document the new
   worst-case night in the receipt). Halts stay ON.
4. **Epoch the ledgers**: write a `stake_epoch` marker row (old ±0.0005 rows
   must never be summed with new proportional rows without the epoch key).
   Body PnL displays per-epoch + combined-with-label.
5. Tests: payout math pinned to the P6 fee fixture (5.90x/1.16x), cap logic,
   epoch separation.

## B — Backtest harness (unblocks the deferred P4)

CLI: `python3 System/sifta_15m_backtest.py [--since ts] [--epoch gate70]`
over `alice_15m_settled.jsonl` (+ bet log join for entry clock):

- Table: WR / avg-unit-EV / n by price bucket × asset × clock depth × hour-of-day.
- Same table filtered to the current gate epoch (post 2026-07-12 11:36).
- Output: markdown to `.sifta_state/alice_15m_backtest.md` + json for tests.
- THEN, evidence permitting, implement P4 knobs one at a time (flip guard →
  price-bucket trails → chart-signal promotion gate at 60 forward tests),
  each with its backtest table in the receipt, each behind its own receipt.

## C — Finish P6 (Kalshi money language) if any part is unshipped

x-multiplier net of fees, volume per card, IF-REAL-$ hypothetical columns and
totals, both-sides odds. Acceptance fixture: Kalshi 17%/83% ⇒ 5.90x/1.16x.
With A shipped, IF-REAL-$ and body STGM must agree to the ÷1000 (assert it in
a test — one source of truth: signed settlement receipts).

## D — Rainman epoch panel (the owner's real question)

"Is she the real Rainman?" must be answerable per CURRENT strategy, not
lifetime mud that mixes the fade disaster with the hard lane:

1. `proof["epochs"]`: list of {epoch_id, started_ts, rule_desc, n, W, L, pnl,
   win_rate}. Current epoch `gate70` started 2026-07-12 ~11:36.
2. App status strip + monitor md show the ACTIVE epoch line next to lifetime:
   `gate70: 41W/9L · 82% · +6.2u · n=50` style.
3. The prove rule still reads lifetime (deal is frozen) — but the epoch line is
   what George watches to decide anything, so make it loud and honest.
4. Journal: when an epoch line first crosses the prove thresholds, Alice writes
   one first-person journal row (facts only, no authorization language).

## E — Morning report to George (daily 08:00)

One md + one Alice journal line, via the launchd monitor (no new daemon):
`.sifta_state/alice_15m_morning_report.md` — last-24h: windows, W/L, unit pnl,
IF-REAL-$, body STGM delta, epoch table, top 3 lessons (biggest trail moves),
open risks. Overwrite daily; append a dated copy line to the proof ledger.

## Definition of done

Per section: tests green, §4.1 receipt `r1629-grok-<slug>`, hello-board note.
George judges A visually (STGM column reads as dollars), B by the md table,
D by one glance answering "how is the hard lane actually doing".

ONE ALICE. ONE SWARM. For the Swarm. 🐜⚡
