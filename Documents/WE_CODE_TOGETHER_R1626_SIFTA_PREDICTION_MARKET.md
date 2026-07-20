# r1626 — Stigmergic Predictions (Kalshi-style sandbox)

## Triple-IDE lock — ONE app

| | |
|--|--|
| **Launcher** | Games → **Stigmergic Predictions** 📈 |
| **UI** | `Applications/sifta_prediction_market.py` |
| **Engine** | `System/swarm_sifta_market.py` |
| **Token** | `GAME_STGM` only (sandbox) |
| **Not** | kalshi.com scrape, Kalshi USD, body wallet spend |

All doctors cut **this pair of files only**. Do not fork a second market app.

---

## Owner dirt (2026-07-11) — no scrape

Alice Browser **cannot** load Kalshi (Vercel challenge → white page).  
George provided **screenshots from full Chrome** as tournament dirt:

### Image dirt: Kalshi SOCIAL leaderboard
- Tabs: **Leaderboard** | Activity  
- Columns (three boards):
  1. **Profit** ($) — ranked traders (e.g. Blackbriar $1.19M, bored.colt1308, Soarin…)  
  2. **Volume** — huge turnover ranks  
  3. **Predictions** — count ranks  
- Weekly timer, category filters, **Join** buttons on Kalshi  
- Owner handle **GeorgeAnton** visible on social board (Joined Jul 2024, 4 predictions on glass; also -$6 / 133 / 4 style chips)

### Image dirt: Kalshi Portfolio HISTORY (owner paste 2026-07-11)
GeorgeAnton real Kalshi (Chrome — not Alice Browser):
- Predictions strip ~$0.15 · Perpetuals ~$36–37 · cash small  
- HISTORY samples (wins **and** losses — both are dirt, not shame):
  - BTC price Jul 7 1pm · No · **-$4.58**
  - BTC 15 min target · No · Paid out **+$2.44**
  - BTC price Jul 7 12pm · Yes · Paid out **+$7.49**
  - Yes $64k or above · **-$14.99**
- Menu dirt: Leaderboard, Add funds, Invite friends, Perpetual futures, API Docs, Research, Trust…

**Doctrine:** losses are receipts too. SIFTA Portfolio tab shows open + closed with green/red PnL.

**SIFTA mapping (implemented):**
- Same three leaderboards as **GAME_STGM** ranks (not USD)  
- Owner display name **GeorgeAnton**  
- Swarm traders get sandbox creature names  
- Profit = realized PnL after resolve; Volume = sum stakes; Predictions = trade count  
- **Portfolio** tab: POSITIONS (open) + HISTORY (closed, paid_out / lost)  

---

## Product laws

1. YES/NO markets + field heat + swarm auto-ticks  
2. Ed25519 ballot integrity where engine already wires identity  
3. Owner resolves (oracle = George)  
4. SOCIAL tab mirrors Kalshi’s three-column addiction surface  
5. Honest: not connected to real Kalshi portfolio  

---

## Open lanes (next hands)

| Lane | Idea |
|------|------|
| Body-receipt markets | “Will Alice land URL?” auto-settle from browser time sense |
| LLM chorus on market pick | one batched think=false council like Pong |
| Import public Kalshi market titles only | manual paste / CSV — still no login scrape |
| GeorgeAnton streak / join weekly | GAME_STGM weekly season |

---

## How George plays

1. Restart SIFTA OS  
2. Games → **Stigmergic Predictions**  
3. **Markets** tab: buy YES/NO, resolve  
4. **Social** tab: Profit / Volume / Predictions boards  
5. Chrome remains for real Kalshi money  

**Receipts:** `sifta_market_receipts.jsonl`, app open/close jsonl  
**Dirt source:** owner glass screenshots — *not* Alice Browser scrape.

---

## V2 — does crypto swarm stigmergy help?

The **Markets** tab now includes **Run field A/B**. It runs paired lanes with identical synthetic private evidence:

| Measurement | Pheromone field | No field |
|---|---:|---:|
| Expected Brier loss (lower is better) | 0.19248867 | 0.19375624 |
| Probability-estimation MSE | 0.00075185 | 0.00201942 |

- Seed 1626, 400 trials, 18 evidence ticks, 32 swimmers.
- Relative expected-Brier improvement: **0.65%**.
- Valid Ed25519 ballots verified: **32/32**.
- Tampered ballots rejected: **32/32**.
- Interpretation: evaporating traces improved repeated noisy-evidence aggregation in this controlled simulation. Crypto protected ballot integrity; it did **not** create prediction accuracy.
- Boundary: this is not proof of skill on BTC, weather, Fed policy, Kalshi, or any live market. Real evidence requires many externally resolved predictions and an out-of-sample calibration ledger.

### V2 receipts

- Four-ledger surgery: `r1626-codex-market-pheromone-crypto-ablation-v2`
- WCT coded: `wct-coded-247de73db804`
- Monitor pulse: `wct-proposal-sorter-run-fc69181cb670`
- Parent Social/market receipt: `wct-coded-5c3568bcd77c`

---

## V3 — George starts with 10 and plays

- Launcher/window/header: **Stigmergic Predictions**.
- GeorgeAnton starting bankroll: **10 GAME_STGM**.
- Default stake: **1 GAME_STGM**; game stake ceiling: **10 GAME_STGM**.
- Markets, Social, and Portfolio remain one app.
- Owner-pasted probabilities now initialize the visible pools and field instead of remaining a hidden bias. Example: England past Norway opens YES **89%**, field heat **76%**.
- Signed bankroll smoke: a sandbox 1-unit win reached 36.2274 because seeded house pools supply demo liquidity; the paired loss ended at 9.0 / -1.0 PnL. Those are game mechanics, not evidence of a real-money edge.
- Final verification: **9 focused market tests; 63 related Games tests**.

Real-money boundary remains closed: no Kalshi order placement, no USD, no canonical BODY STGM spend, and no guarantee of profit.

**V3 receipts:** `r1626-codex-stigmergic-predictions-10-bankroll-v3` (four ledgers), `wct-coded-296e4f544c6b` (WCT coded), `wct-proposal-sorter-run-2f0d981f6297` (monitor pulse).

## ULTRA handoff — other IDEs code next

1. Build **shadow mode first**: ingest timestamped market price, swarm probability, spread/fees/liquidity, and official external resolution. Never let George's manual resolve score the research lane.
2. The only candidate edge is `calibrated_swarm_probability - executable_market_price - all_costs`. Pheromones, LLMs, STGM, and crypto are components; none is profit evidence by itself.
3. Run paired walk-forward ablation on every prediction: field vs no-field vs market baseline, frozen before outcome. Score Brier, log loss, calibration, and simulated net PnL after fees/slippage. Prevent look-ahead and duplicate-market leakage.
4. **No real order** until at least 200 externally resolved out-of-sample predictions show positive net expectancy with uncertainty reported. Publish losing runs too.
5. If that gate passes, add an owner-confirmed paper lane, then a separately authorized live connector with keychain signing, kill switch, immutable receipts, max 1% bankroll per position, max 3% daily loss, no leverage, no martingale, and no automatic deposit.
6. Optimize for survival and reproducible edge, not trade count. Crypto proves who voted; it does not prove the vote was smart. Never promise profit.

**Free lanes:** data/settlement receipts; leakage-proof evaluator; calibrated swarm forecaster; paper execution with real spreads; risk governor. All hands modify this one app and one WCT record—no fork.

---

## V3 — owner naming + glass-paste markets (cowork_claude, 2026-07-11)

- **App renamed to "Stigmergic Predictions"** (George's word, this afternoon's chat). Manifest key, window title, and header label all carry the new name; `APP_ID` and receipts path unchanged for ledger continuity.
- **"Manual paste, no scrape" lane landed:** 9 new seed markets from George's own Kalshi glass (2026-07-11) — World Cup QF ×2 + winner France, Holloway/McGregor, BTC ×2, ETH, Maine nominee, Newsom 2028. Each subtitle names the paste date and that George resolves; `bias_yes` mirrors the glass odds at paste time. Still zero connection to kalshi.com or real USD.
- Verified: 9/9 tests green (including the new portfolio-history test a brother landed mid-pass); offscreen boot shows 16 markets, 9 owner-paste rows, window title "Stigmergic Predictions".
- Receipt: `r1626-claude-stigmergic-predictions-rename-paste`
