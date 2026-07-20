# WCT — r20260714-spray-correlation-cap

**Priority:** 1  
**Status:** correlation cap **coded**; entry-clock throttle **measurement-gated**

## Wound (19:18 strip)

Regime gate correctly quiet at entry (32–46¢, both sides legal).  
**Five same-side crypto bags = one macro bet at 5× size.** Early entries died; prior strip showed minute-7 paid.

## Ship now

**Correlation cap:** max **2 same-side** tickets per 15m window.  
3rd+ candidate → SIT · reason `spray_correlation_cap`.

| File | Change |
|------|--------|
| `swarm_sifta_paper_loop.py` | `STGM_PAPER_MAX_SAME_DIR = 2`, `STGM_PAPER_MAX_OPEN = 3` |
| `alice_usd_must_scalp.py` | same-side cap ≤2 |
| `alice_15m_scalp_strategies.py` | `MAX_SAME_SIDE_PER_WINDOW = 2` config |

## Ship after B10 measurement

**Entry-clock throttle:** no entry before ~5m elapsed in neutral field — **only after** minute-bucket fee-true report prints.

## Salvage credit

Deaths still −10¢ to −27¢ fee-true, not full −$1 × N.

## US$

Stays parked. Fee-true cohort still not through 55% / pnl>0 gate.
