# WCT plan — r20260714-salvage-exit-red-field

**Alice implements.** STGM/paper only. US $ HAND HALT stays. Pairs with regime gate.

## Wound

Green-only exit rides dead tickets to zero. BNB DOWN @ −35¢ vs ~98% UP field
donates full stake. Loss tail (avg −0.49) vs win (+0.19) is the deficit.

## Fix

When **held-side implied ≤ 0.30** and **secs left > 90**:

- Exit at **quoted side bid** (residual banked)
- Tag `why` / cohort = `salvage_exit_red_field` (honest learner stats)
- Thresholds in config: `SALVAGE_SIDE_IMPLIED_MAX`, `SALVAGE_MIN_SECS_LEFT`

Together with regime gate: **enter with the field · stop paying full fare when wrong**.

## Files

- `System/alice_15m_scalp_strategies.py` — `salvage_exit_should_fire` / intent / `_exit_if_open`
- `System/alice_15m_scalp_learner.py` — paper execute path
- `System/alice_15m_scalp_lab.py` — uses strategy exits (inherits salvage)
- `tests/test_alice_15m_scalp_salvage_exit.py`

## Acceptance

- BNB replay (DOWN, yes=0.98, 500s left) → salvage fires
- Side implied 0.45 → no-fire
