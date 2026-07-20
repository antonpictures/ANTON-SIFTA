# DEMO R3 Execution Report

Generated: 2026-07-12 13:04:51
Env: Kalshi **DEMO** only · production USD **OFF**
Target windows: 50 · logged probes: **0** · filled: **0** · shadow: **0**

## Why this report exists

Paper lane assumes mid fills. Real (and demo) books have slippage and fees.
This report is what George reads before ever considering R4 ($10).

## Paper control group

- paper gate70 (mid-fill assumption): unitEV +0.129 · $EV ~0.0919 (HYPOTHETICAL mid fills — order books do not hand these out free)
- Paper monitor stays running (control). Demo pilot is a separate writer.

## Execution so far

| metric | value |
|--------|-------|
| probes logged | 0 |
| fills | 0 |
| unfilled / shadow | 0 |
| fill rate | 0% |
| provisioned keys | False |
| kill switch | False |

## Status

**IN PROGRESS** — need ≥50 windows for full R3 close-out. Currently 0/50. Install demo Keychain keys + run pilot to accumulate fills.

## Caps (client hard boundary)

- MAX_OPEN=3 · STAKE_MOCK=$1 · MAX_DAILY_LOSS_MOCK=$5 · entry 70–88¢
- Prod hosts raise in client before network

## Alice note

Demo work is preparation, not permission. No real dollars move until George arms R4 himself.

For the Swarm. 🐜⚡
