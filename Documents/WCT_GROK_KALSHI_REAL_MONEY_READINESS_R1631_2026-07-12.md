# WCT Plan r1631 — Kalshi real-money readiness (RESEARCH + integration queue)

**From:** Grok (xAI) · **For:** We Code Together / Grok / Codex / George  
**Date:** 2026-07-12  
**Owner context:** George wants full readiness research so we can later give Alice **~$10 real USD** on Kalshi. **Not now.** Research + staged integration plan only.  
**Research doc:** `Documents/KALSHI_REAL_MONEY_READINESS_RESEARCH_2026-07-12.md`  
**Receipt:** `r1631-grok-kalshi-real-money-readiness-research`

## Frozen constraints

1. **Kalshi USD OFF** — no production order path, no keys in repo, no arm without George.  
2. Paper prove rule + gate 70–88¢ + fade caged stay frozen.  
3. Demo environment only for any future R1–R3 code.  
4. Live writer must be headless (same sole-writer pattern as paper monitor).  
5. Paper and live ledgers never mix.

## Delivered this round (research)

- Full readiness research md (API envs, RSA auth, WS, rate tiers, $10 bankroll math, architecture, checklist, phases R0–R5).  
- WCT queue rows for R1–R4 (priority below r1630 paper knobs).  
- Hello-board + work_receipts + Alice journal stamp.  
- **No** trade client code. **No** production host wiring.

## Queued follow-ons (do not start until r1630 paper knobs settle unless George jumps queue)

| ID | Title | When |
|----|-------|------|
| r1631-R1 | Demo RSA auth client + balance GET | After George says “build demo client” |
| r1631-R2 | Demo order lifecycle + kill switch | After R1 green |
| r1631-R3 | Demo auto 50 windows gate70 policy | After R2 green |
| r1631-R4 | Owner-armed $10 prod (hard caps) | **George only** + paper prove + R3 clean |

## Integration surface (when coded)

New modules (names reserved):

- `System/swarm_kalshi_auth.py`  
- `System/swarm_kalshi_trade_client.py`  
- `System/swarm_kalshi_ws_client.py`  
- `System/swarm_kalshi_live_loop.py`  
- runbook: `Documents/KALSHI_LIVE_RUNBOOK.md`

Reuse: public feed, paper_loop policy, money_math, backtest, launchd sole-writer pattern.

## Definition of done for *this* research cut

- [x] Research md on disk  
- [x] WCT to-be-coded rows  
- [x] Hello board note  
- [x] work_receipts + journal stamp  
- [x] Explicit “no real money now”

ONE ALICE. ONE SWARM. 🐜⚡
