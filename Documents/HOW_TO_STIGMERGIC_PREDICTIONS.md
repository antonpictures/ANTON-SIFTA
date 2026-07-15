# How to use Stigmergic Predictions (dual lane)

**What it is:** Alice’s 15m crypto prediction surface — **STGM/paper learning** always, **Kalshi US$** only when lane + kill allow.

**What it is not:** Free money. Paper green ≠ US$ edge until dual-lag parity is measured.

## Open it
SIFTA → Programs → **Stigmergic Predictions** / prediction glass  
(`Applications/sifta_prediction_market.py`)

## Two lanes

| Lane | Button / state | Money |
|------|----------------|--------|
| **STGM ON** | Paper + body STGM micro | Learning only |
| **US $ LANE** | OFF by default | Real Kalshi predictions cash |

Kill switch: `.sifta_state/kalshi_kill_switch.json` (`halt: true` = no US$ writes).

## First 60 seconds (safe)
1. Confirm **US $ LANE OFF** if you are not intentionally live.  
2. Watch **OPEN — STGM** (live paper bags) and **HISTORY** (SCALP / HOLD / TRAIN).  
3. Pink scalp strip is **selection-biased** (greens that got a fee-true quote) — not full-lifecycle EV.  
4. Kalshi.com portfolio is truth for **cash**; glass hyp $ is not exchange balance.

## Doctrine (July 2026 · Chapter XXXV)

### Exit (priority order)
1. Fee-true **green TP**  
2. **Salvage** — side implied ≤ 0.30, >90s left → bid exit  
3. **Soft adverse** — side implied ≤ 0.42, <180s, bid ≥ entry−15¢  
4. **Force-flat** ≤ 7:30 left  

### Entry
- **regime_gate** — do not fade ≥70% field  
- Band **40–65¢** on US$  
- Sit is valid  

Shared code: `System/alice_15m_scalp_strategies.py`  
US$ uses the **same** functions: `alice_usd_must_scalp.py` · `alice_usd_take_profit.py`

## Dual-lag harness
```bash
python3 -c "from System.alice_usd_dual_lag_harness import run_dual_shadow_suite; print(run_dual_shadow_suite(n=20))"
```
Stream: `.sifta_state/alice_usd_dual_lag_stream.jsonl`  
Does **not** place US$ by itself.

## Before turning US $ ON
1. Parity tests green (`tests/test_alice_usd_parity_and_dual_lag.py`)  
2. Shadow lag suite run  
3. Night loss cap set; **one bag · $1** first on ~$20 bank  
4. Owner deliberately clears kill + arms lane  

## Buttons / surfaces
| Control | Does |
|---------|------|
| **STGM ON / pause** | Paper learning loop |
| **US $ LANE ON/OFF** | Real money hand |
| **AMMO** | $ per ticket (start $1 for live reopen) |
| **Sync / Refresh** | Marks / glass |

## Honest money rule
- **GAME_STGM / body STGM** = organism learning skin  
- **US$** = Kalshi predictions cash only when armed  
- **TRAIN** rows = shadow Alice, never real $  

## Focused tests
```bash
python3 -m pytest \
  tests/test_alice_15m_scalp_regime_gate.py \
  tests/test_alice_15m_scalp_salvage_exit.py \
  tests/test_alice_usd_parity_and_dual_lag.py \
  tests/test_alice_15m_scalp_lab_r1684.py -q
```

## Docs
- README **Chapter XXXV**  
- `Documents/WCT_CLAUDE_GREEN_SCALP_UNKNOWNS_2026-07-14.md`  
- `Documents/WCT_ALICE_UPDOWN_REGIME_ALIGN_2026-07-14.md`  
- `Documents/WCT_ALICE_SALVAGE_EXIT_RED_FIELD_2026-07-14.md`  

For the Swarm. 🐜⚡
