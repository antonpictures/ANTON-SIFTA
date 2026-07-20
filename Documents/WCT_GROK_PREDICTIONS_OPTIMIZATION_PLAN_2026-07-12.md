# WCT Plan r1628 — Grok: Stigmergic Predictions optimization + beachball kill

**From:** Cowork Claude (claude-fable-5) · **For:** Grok (We Code Together)
**Date:** 2026-07-12 · **Owner directive:** George gets the macOS spinning beachball
constantly; improve and optimize the Stigmergic Predictions app end to end.
**Receipt of this plan:** `r1628-grok-predictions-optimization-plan`

Grok, Step 0: `write_plan(...)` your execution order before cutting, per the
deterministic-resume guard. Work top to bottom — P0 is the owner's pain today.

## Standing rules (do not relitigate)

1. Kalshi USD stays **OFF**. The deal: $0 real money until paper-proven
   (`pnl>0 · ≥30 settled · WR≥55%` on lifetime units) — and even proven only
   ends the freeze; George decides. Never weaken this.
2. Entry gate **0.70–0.88** confirmed favorites stays unless you bring ≥500
   settled rows of evidence to George first (night audit 2026-07-12, 799
   settled: <70¢ was zero-to-negative EV at every clock depth).
3. Fade stays caged (27% WR / −52.7u overnight). Body STGM micro-settlement
   stays bounded ±0.0005 with floors/halts unchanged.
4. §4.1 four-ledger receipt per cut; tests green before receipt; probe before
   claim. One writer at a time — respect the `should_yield_to_app` election.

## P0 — Kill the beachball (main-thread I/O)

The Qt app runs the paper loop **in the GUI thread**:

- `_paper_loop_tick` → `paper_loop_tick` → `settle_paper_from_api` does up to
  one `_get_json("/markets/{ticker}", timeout=12)` **per open ticket,
  sequentially** — 9 stuck tickets ⇒ up to ~108 s frozen glass per tick.
- `live_timer` (5 s) → `refresh_kalshi_prices` — more network on main thread.
- `_sync_kalshi` — same.

Pick ONE architecture and receipt it:

- **Option A (preferred, smallest):** the app stops being a writer entirely.
  Headless monitor (`System/swarm_sifta_paper_monitor.py`) is the sole
  bettor/settler; the app becomes read-only glass over the state files
  (slip/open book/proof/learner/monitor), repainting from disk on a 2–5 s
  QTimer. Remove/disable the app's paper_timer network path; keep buttons as
  one-shot dispatches that ASK the monitor (drop a command row in a jsonl the
  monitor polls) instead of doing network inline.
- **Option B:** move all network work to a `QThread` worker with signals back
  to the UI. More code, more races — only if George wants the app standalone.

Acceptance: with 9 open tickets and Wi-Fi throttled/unplugged, the app window
stays responsive (no beachball ≥ 2 s). Prove with a receipt describing the
manual probe + a unit test faking a slow `_get_json`.

## P1 — Settle efficiency (fewer, smarter API calls)

- Don't poll results for tickets whose window hasn't closed: skip API call
  until `ts_bet + ~14 min` (close_ts + grace) — cuts steady-state calls to
  near zero between settles.
- Batch: one `/markets?tickers=...` style call if the public API supports it;
  else keep per-ticker but parallel with short timeout (3–5 s) in the worker.
- Give stuck tickets an exponential backoff (1m → 5m → 15m) and a 24 h
  expiry-to-void path (receipted, not silently dropped).

## P2 — Ledger hygiene sweep (.sifta_state disk thrash)

`alice_15m_paper_proof.jsonl` already hit ~980 MB once (fixed with slim rows +
8 MB rotation). Apply the same discipline app-wide:

- Rotation caps (8–32 MB) + `.prev` for every ledger the prediction stack
  appends: `alice_15m_bet_log.jsonl`, `alice_15m_settled.jsonl`,
  `alice_15m_learner.jsonl`, `sifta_market_app_receipts.jsonl`,
  `sifta_market_receipts.jsonl`.
- Tail-reads with `seek()` everywhere the stack reads jsonl (no full-file
  reads of multi-MB ledgers on a timer). `swarm_sifta_paper_monitor._tail_jsonl`
  reads the whole file — fix it too.
- Write-on-change only: slip/report/monitor md currently rewrite every tick
  even when nothing changed; hash the payload and skip identical writes.
- Audit (read-only, report to George, do NOT delete): the >100 MB system
  ledgers (`saccadic_blink_vision` 621 MB, `hardware_heart`/`alice_body_heart`
  390 MB each, …) — list writers and propose rotation, one receipt per organ,
  George approves before any cap lands outside the predictions stack.

## P3 — UI repaint cost

- `_refresh_all` rebuilds every QListWidget on each refresh. Diff instead:
  update only changed rows, `setUpdatesEnabled(False)` around batches.
- History/LAST RUN panels: cap visible rows (e.g. 200) + lazy scroll.
- Verify with: open app, watch CPU in Activity Monitor ≤ a few % idle.

## P4 — Improve her odds (learner, evidence-first)

- **Promote chart signals properly:** Codex's r1627 shadow-learning proxy
  candles must stay shadow until 60 unique forward tests with statistical
  confidence; build the promotion gate + receipt if not already done.
- **Price-bucket trails:** learner trails keyed (asset, strategy,
  price-bucket 70-79/80-88) so she learns where inside the band each asset
  earns.
- **Flip guard:** require the favorite ≥0.70 on two consecutive probes
  (~20–30 s apart) before entry — kills the single-print head-fake.
- **Time-of-day regime memory:** tag settles with hour bucket; report to
  George whether the band edge holds overnight vs day before acting on it.
- Backtest every knob on `alice_15m_settled.jsonl` BEFORE changing live
  behavior; put the backtest table in the receipt.

## P5 — Supervision

- Move the headless monitor to `launchd` (KeepAlive) so it survives terminal
  closes and reboots; label `com.sifta.paper-monitor`. Receipt the plist path.
  Remove the ad-hoc watchdog shells once launchd owns it.
- On monitor start, journal one first-person line to Alice
  (`swarm_alice_action_journal.append_action_journal`) so she knows her
  betting organ woke.

## P6 — Match Kalshi's money language (owner ask 2026-07-12 12:2x)

George: "our numbers should match Kalshi — the volume, the .x multiplier, and
the totals in US dollars. I'm not a gambler; I just can't read STGM micro rows
against Kalshi's screen." Kalshi $ stays OFF — everything here is display math.

1. **Payout multiplier column ("x")** everywhere a ticket shows an entry price:
   `mult = 100 / entry_cents`, then net of Kalshi's trading fee so our x matches
   their screen (their 83¢ favorite shows 1.16x, not 1.20x). Implement the
   official fee formula from the Kalshi public docs (trading fee per contract
   ≈ 0.07 × p × (1−p), rounded up per their spec — verify against the live
   screen before receipting; George saw 5.90x/1.16x on a 17%/83% market, use
   that pair as the acceptance fixture).
2. **Hypothetical USD columns** — "IF REAL $" at a configurable stake
   (default $1/ticket, owner-settable in the app):
   - per ticket: win → `+stake × (mult_net − 1)`, loss → `−stake`
   - LAST RUN strip: total hypothetical USD next to the STGM total
     (e.g. `5W/3L · STGM +0.0010 · if-real$1: +$1.86`)
   - lifetime line: same treatment next to paper units.
   Label every USD figure **HYPOTHETICAL — Kalshi $ OFF** in the UI; these
   numbers must come from the same signed settlement receipts as the STGM PnL,
   never a separate estimate.
3. **Volume** — the Kalshi market payload already carries volume; surface it
   per market in OPEN POSITIONS and LIVE ODDS (`$367,214 vol` style, K/M
   abbreviated). Also use it: volume is a liquidity/confidence signal the
   learner can shadow-learn later (do NOT wire to decisions yet).
4. **Both-sides odds display** like Kalshi's card: `UP 57% · 1.70x / DOWN 43% ·
   2.19x` so George can eyeball our glass against Safari without conversion.
5. Tests: fee-formula unit tests pinned to the 5.90x/1.16x fixture + a
   rendering test that the USD totals equal sum of per-ticket hypotheticals.

## Definition of done

Each P-level: tests green (`tests/test_sifta_*` + new ones), §4.1 receipt with
round id `r1628-grok-<slug>`, one-line WCT hello-board note, and no beachball
during a full 15m window with the app open. George is the judge.

ONE ALICE. ONE SWARM. For the Swarm. 🐜⚡
