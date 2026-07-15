# WCT plan — r20260714-updown-regime-align

**Alice implements.** STGM/paper only. US $ HAND HALT stays.

## Wound

2026-07-14 **16:47–16:50**: 6/6 tickets **DOWN** (BTC BNB SOL XRP DOGE ETH) died
while Kalshi **UP** implied **69–99%**. Buy-low / fade was shorting a strong up-drift.
Break-even WR ~72% — fade cannot survive that regime.

## Fix

`regime_gate` in `System/alice_15m_scalp_strategies.py`:

- Config: `REGIME_GATE_IMPLIED_THRESH = 0.70` (not buried magic)
- No **DOWN** when UP implied ≥ thresh and field agrees UP
- Symmetric: no **YES** when DOWN implied ≥ thresh and field agrees DOWN
- Skip ticket/window is a valid win (no forced fade)

Wired into:

- strategy `_enter`
- paper loop side selection (`swarm_sifta_paper_loop.py`)
- lab enter double-check (`alice_15m_scalp_lab.py`)

## Acceptance

`tests/test_alice_15m_scalp_regime_gate.py` — 16:47 six-DOWN window → zero DOWN pass.

## Constraints

- No USD path / lane-state changes
- Does not replace formula-audit P0s — side-selection guard on top
- No trade quota
