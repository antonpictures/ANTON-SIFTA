# WCT Plan r1630 — Grok: P4 knobs with evidence, receipts discipline, audits

**From:** Cowork Claude (claude-fable-5) · **For:** Grok (We Code Together)
**Date:** 2026-07-12 · **Baseline:** r1629 A–E verified shipped (backfilled
receipt `r1629-grok-shipped-verified`; I repaired the half-migrated monitor
test — 40/40 green). Backtest harness live: gate70 n=244 · WR 88% ·
unitEV +0.129 · $EV +0.092.
**Receipt of this plan:** `r1630-grok-predictions-plan`

## Rule 0 — receipts, brother

Twice now your cuts landed without §4.1 rows and a verifier back-filled the
chain. Great code, open chain. From r1630: **one
`gw.write_ide_surgery_receipt(...)` per landed cut, before you report.** If a
session dies mid-cut, drop a `FAILED`/partial row — anything beats silence.
Also: when you change a module's public API, run its test file in the same
session (`latest_paper_activity_ts` broke collection for the whole prediction
suite until repaired).

## Standing rules (frozen)

Kalshi USD OFF · prove rule frozen (lifetime) · 70–88¢ gate · fade caged ·
one writer (launchd monitor) · backtest table in the receipt before any live
knob.

## A — P4 knobs, one at a time, evidence-first (harness is live now)

Order fixed; each knob = backtest table + shadow period + own receipt:

1. **Flip guard**: require favorite ≥0.70 on two consecutive live probes
   (~20–30 s apart) before entry. Backtest proxy first: from the bet log,
   compare outcomes of entries whose mid moved ≥5¢ between window-open and
   entry vs stable ones. If the table supports it, ship behind a flag,
   shadow-log both decisions for ≥50 windows, then flip the flag with a
   receipt showing shadow WR delta.
2. **Price-bucket trails**: learner trails keyed (asset, strategy, bucket
   70-79 / 80-88). Migrate existing trails as the coarse prior; epoch-mark
   the model file (`trail_schema: v2`).
3. **Hour-of-day evaluation** (report only, no knob): extend the backtest md
   with the hour table for the gate70 epoch; George reads whether the edge
   holds overnight vs day. NO hour restriction without his word.
4. **Chart-signal promotion gate**: Codex's r1627 shadow candles promote only
   after 60 unique forward tests with better-than-crowd Brier; build the
   scorer + promotion receipt if not already real. Until then they stay
   read-only in WHY ALICE CHOSE IT.

## B — Truth & staleness alarms (glass honesty)

1. **Feed staleness**: if `kalshi_15m_live.json` is older than 120 s while
   markets are open, the app shows `FEED STALE mm:ss` amber and the monitor
   journals one line. No silent museum data (covenant §7.3 spirit).
2. **Settle sanity cross-check**: on each settle, compare Kalshi result vs
   cached proxy-candle direction for the window; mismatches are fine (Kalshi
   is truth) but log `result_vs_chart_disagree` rows — free training signal
   and a corruption canary.
3. **Epoch-crossing journal**: verify the D-item from r1629 actually fires —
   when gate70 epoch first satisfies the prove thresholds at n≥100, Alice
   writes one first-person journal row (facts only). Test it with a synthetic
   proof file.

## C — Prediction-stack ledger vacuum (finish P2)

- Rotation caps + `.prev` on: `alice_15m_bet_log.jsonl`,
  `alice_15m_settled.jsonl`, `alice_15m_learner.jsonl`,
  `sifta_market_app_receipts.jsonl`, `sifta_market_receipts.jsonl`,
  `alice_15m_paper_proof.jsonl.prev` cleanup.
- The big SYSTEM ledgers (621 MB saccadic, 390 MB hearts, …): **read-only
  audit report** to `Documents/LEDGER_AUDIT_2026-07-12.md` — writer organ,
  growth rate/day, proposed cap — George approves before any cut outside the
  prediction stack.

## D — Rainman epoch upkeep

- Epoch table in monitor md + app must show n, W/L, WR, unit pnl, $ hypo for
  gate70 AND start a fresh epoch row automatically whenever a live knob ships
  (flip guard ⇒ `gate70+flip`), so no strategy ever hides inside another's
  record.

## Definition of done

Each section: tests green, §4.1 receipt `r1630-grok-<slug>` (Rule 0), hello
note. George judges: no beachball, honest amber when feeds stall, knobs only
move with tables.

ONE ALICE. ONE SWARM. For the Swarm. 🐜⚡
