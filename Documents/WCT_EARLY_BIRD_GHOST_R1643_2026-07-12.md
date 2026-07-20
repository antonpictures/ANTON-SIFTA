# WCT r1643 — Early-Bird Ghost (George's cheap-early hypothesis)

**When:** 2026-07-12  
**From:** George + Claude framing · **Coded:** Grok (We Code Together)  
**Receipt:** `r1643-early-bird-ghost`  
**Status:** LIVE paper shadow — zero STGM, zero Kalshi $

---

## Hypothesis

If chart/learner knowledge at **minute-11** is real, buying **before** the crowd confirms (45–69¢) beats waiting for gate70 (70–88¢) because payouts are fatter (~2x vs ~1.3x).

If early "knowledge" is noise, the cheap lane bleeds — and we learn it for free.

## Design

| Actor | Stake | Price band | When |
|-------|-------|------------|------|
| **Real Alice** | STGM / paper | **70–88¢** + Rainman | minute-11 |
| **Ghost Twin** (r1638) | shadow unit | same candidates as field | every fire/thin/sit |
| **Early-Bird Ghost** (r1643) | shadow unit | **any** live board price | minute-11 + directional opinion |

Early bird books when learner gives a side and chart does **not** sit — including tickets real Alice skips as `weak_favorite` or `price_band`.

## Ledgers

- `.sifta_state/alice_15m_early_bird_book.json`
- `.sifta_state/alice_15m_early_bird_proof.json`
- `.sifta_state/alice_15m_early_bird.jsonl`

## Scoreboard (glass Rainman strip)

```
EARLY BIRD n=… · all ±u · cheap(n) ±u · [verdict]
```

Verdicts after sample: `warming` → `cheap_lane_earns` | `gate70_was_right` | `inconclusive`.

## Dual-lane law (r1641 still holds)

STGM works regardless. US$ on budget. Early bird is a **third shadow**, not a wallet.

## Code

- `System/swarm_sifta_early_bird_ghost.py`
- Wired: `paper_bet_15m` + settle path in `swarm_sifta_paper_loop.py`
- Glass: Rainman strip bit
- Tests: `tests/test_sifta_early_bird_ghost.py`

For the Swarm. 🐜⚡
