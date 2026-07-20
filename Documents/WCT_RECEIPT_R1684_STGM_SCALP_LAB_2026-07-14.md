# WCT Receipt r1684 — STGM 15m intrawindow scalp laboratory (implementation)

**Date:** 2026-07-14  
**Owner direction:** Bank fee-true greens mid-window (cash-out organ); lab finds more patterns in STGM with Kalshi-realistic fills.  
**USD:** Lab never places, routes, or signs real-USD orders. Live cash-out remains `alice_usd_take_profit` under owner caps.

## Receipts landed

| ID | Module | Status |
|----|--------|--------|
| `r1684-a-scalp-proof-accounting` | `System/alice_15m_scalp_proof_accounting.py` | Done |
| `r1684-b-execution-tape` | `System/alice_15m_execution_tape.py` | Done (BBO bootstrap) |
| `r1684-c-kalshi-execution-sim` | `System/alice_15m_execution_sim.py` | Done (taker walk + maker conservative) |
| `r1684-d-scalp-strategy-tournament` | `System/alice_15m_scalp_strategies.py` + lab | Done (6 frozen arms) |
| `r1684-e-scalp-holdout-gate` | `alice_15m_scalp_lab.evaluate_holdout_gate` | Done (300w/500 fills; USD never) |
| `r1684-f-scalp-glass` | glass JSON/MD via lab | Done |

## Files

- `System/alice_15m_scalp_proof_accounting.py` — honest vs legacy; selection-bias disclaimer
- `System/alice_15m_execution_tape.py` — append-only tape from live marks
- `System/alice_15m_execution_sim.py` — deterministic sim + ledger `alice_15m_scalp_orders.jsonl`
- `System/alice_15m_scalp_strategies.py` — 6 arms, policy hash, 0–3 RT/window
- `System/alice_15m_scalp_lab.py` — tick hook, tournament, holdout, glass
- `System/swarm_sifta_paper_loop.py` — wires `tick_scalp_lab` each monitor cycle
- `System/alice_usd_take_profit.py` — r1684 mid-window bank-greens lesson sticky
- `System/alice_15m_scalp_learner.py` — MD banner: biased WR
- `tests/test_alice_15m_scalp_lab_r1684.py` — offline suite

## Tests

```bash
python3 -m pytest tests/test_alice_15m_scalp_lab_r1684.py tests/test_alice_15m_scalp_learner.py -q
# 20 passed
```

## Live USD doctrine (unchanged path, clarified)

- One-ticker dual lane under caps.
- **Take-profit every fee-true green opportunity** (min edge $0.03), not force-trade every window.
- Do **not** wait for settlement when cash-out is green.
- Glass can show direction red while cash-out already banked green (owner BTC example).
- Grok force-fills stay out of auto cohort attribution.

## Still open (Ken-friendly help list)

1. **Full multi-level REST orderbook poll** at sub-15s (rate limits + gap recovery) — tape today is BBO synthetic from `kalshi_15m_live.json`.
2. **Authenticated WS deltas** (read-only) with sequence gap recovery — not started.
3. **Fill-model calibration** vs real public trades / Safari tape fixtures.
4. **Block-bootstrap CI on real chronological holdout** once ≥300 windows / 500 RTs accumulated.
5. **Latency stress matrix** (250/500/1000 ms + p95 gap) as scheduled offline job, not only live tick.
6. Optional: glass widget surface for `alice_15m_scalp_glass.md` in desktop UI.

## Statement

No USD order path was called by the laboratory modules. Promote gate `usd_authorize` is hard-coded `False`.

## Owner pattern to amplify

BTC force entry → Alice `reduce_only` cash-out on fee-true green → bank mid-window.  
Hold-to-end would have suffered path death on glass. **Repeat TP pattern; lab arms hunt the next edges.**
