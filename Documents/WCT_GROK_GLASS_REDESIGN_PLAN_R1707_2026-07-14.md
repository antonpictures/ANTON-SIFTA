# WCT Plan r1707 — Grok: predictions glass redesign (SCALP/HOLD lanes made visible)

**From:** Cowork Claude (`claude-fable-5`), for George → Grok in We Code Together
**Date:** 2026-07-14
**Round:** `r1707-grok-glass-scalp-hold-redesign`
**Owner direction (George):** The HISTORY glass reads like one mixed list. Scalps land unlabeled, there is no fee-true $ column, no dedicated STGM SCALP strip, and shadow-training scalps are invisible. Redesign the predictions glass so the two lanes and the three row species — HOLD / SCALP / TRAIN — are unmistakable at a glance.

---

Grok, this is your round. Step 0 before any edit:

```
write_plan("r1707-grok-glass-scalp-hold-redesign: propagate mode/fee-true from settled ledger to glass, badge HISTORY rows SCALP/HOLD, add STGM SCALP strip, surface TRAIN rows, lane headers STGM vs US$")
```

so the deterministic-resume guard applies if your session drops.

## Ground truth I probed today (OBSERVED, 2026-07-14)

- `.sifta_state/alice_15m_settled.jsonl` — every settled row already carries `mode` (`scalp_execute` on 5 of the last 60), `force_flat`, `pnl_usd_fee_true`, `fees_total`, `fee_model`. The data exists; the glass ignores it.
- `.sifta_state/alice_15m_paper_proof.json` — `history` rows carry the same `mode` + `pnl_usd_fee_true`.
- `Applications/sifta_prediction_market.py` — the HISTORY table columns are defined near line 1323 (`["RESULT","MARKET","BET","¢","x","$ HYP","ENTERED","WHY","PnL STGM"]`) and painted near lines 2309–2360. No mode, no fee-true, no force-flat anywhere.
- The snapshot builder `body_results` (near line 483) joins `alice_15m_settled.jsonl` by ticker but drops `mode`, `force_flat`, and `pnl_usd_fee_true` when it builds the glass row. This is the single choke point — fix it once and every table downstream can paint the truth.
- Scalp ledgers already live: `.sifta_state/alice_15m_scalp.jsonl` (~1.7 MB), `alice_15m_scalp_training_book.json`, `alice_15m_scalp_glass.json` / `.md`, `alice_15m_scalp_lab_report.json`, `alice_15m_scalp_proof_honest.json`.
- Honest-evidence caveat from r1684 stands: the scalp proof file is selection-biased (exits recorded only after a fee-net green quote). Any strip you build must carry that caveat, not a victory lap.

## The cuts, in order

### Cut 1 — Propagate (smallest live cut, do this first)
In `body_results` (sifta_prediction_market.py ~line 483), copy `mode`, `force_flat`, `pnl_usd_fee_true`, `fees_total` from the joined settled row into the glass row dict. No new files, no new ledgers.

### Cut 2 — HISTORY badges + fee-true column
- Badge every HISTORY row: `SCALP` (gold, from `mode == "scalp_execute"`), `HOLD` (default). Force-flat rows get a `⚑ FLAT 7:30` marker (from `force_flat`).
- Add a `FEE-TRUE $` column from `pnl_usd_fee_true` (signed, colored). Rows without it paint `—`. Keep the existing `$ HYP` column — it is the hold-to-settle hypothetical and stays labeled as such (tooltip already says HYPOTHETICAL · Kalshi $ OFF).
- Apply the same badge to the LAST RUN strip rows (painted ~line 2220).
- Respect the column-width discipline: use `_fit_table_columns`, do not let money columns squash (George's squeeze screenshot rule is in the comments).

### Cut 3 — STGM SCALP strip
A compact strip (same density as the LAST RUN strip) fed by `alice_15m_scalp_glass.json`: today's executed-scalp count, fee-true $ sum, W/L, force-flat count. One dim caveat line from `alice_15m_scalp_proof_honest.json` — selection-biased sample, not an executable-edge proof. No wall of prose; George's eyes-hurt rule is law in this file.

### Cut 4 — TRAIN rows visible
Shadow-training scalps from the training book / `alice_15m_scalp.jsonl` surface as dim `TRAIN`-badged rows — either a toggle on the HISTORY panel or a separate mini-table under the SCALP strip. They must never mix into the settled STGM book unlabeled: training is learning food, not P&L.

### Cut 5 — Lane headers
Rename the panel headers so the lanes read instantly: `HISTORY — STGM (paper learning)` and keep the US$ mirror clearly labeled `US$ (real cash · Kalshi)`. When the dual mirror copies a paper ticket into a US$ twin, mark the paper row with a `⇄ DUAL` marker so George can trace the pair.

## Guardrails (binding)

- Glass-only round. No order paths, no routing, no signing, nothing that touches real-USD execution. The r1684 boundary is unchanged.
- Extend the existing tables and snapshot builder; do not fork a rival widget or a rival ledger (§1.B — reuse before rival).
- Ledgers are append-only; you read them, you never rewrite them.
- Badges and columns, not prose. Hidden `learn_lbl` stays hidden.
- If a field you expect is missing on old rows, paint `—`; never invent a value (§6 tool truth).

## Acceptance (screenshot-verifiable)

1. Every HISTORY row shows SCALP or HOLD; scalp rows show a fee-true $ figure; force-flat rows show the flag.
2. The STGM SCALP strip is visible with fee-true $ sum and the honesty caveat.
3. TRAIN rows appear, labeled, and are visually distinct from settled rows.
4. Lane headers name STGM vs US$; a dual-mirrored row carries `⇄ DUAL`.
5. A test covers Cut 1: settled row with `mode=scalp_execute` + `pnl_usd_fee_true` propagates into the snapshot row. Run the existing prediction-market tests green or report the honest failure.
6. §4.1 four-ledger fan-out receipt via `System/swarm_predator_gate_writer.write_ide_surgery_receipt`, round id `r1707-grok-glass-scalp-hold-redesign`, naming files touched and tests run.

One list, three species, two lanes — and George never has to wonder again whether a green row was a settled hold, a mid-window scalp, or a training ghost.

For the Swarm. 🐜⚡
