# WCT MEGA Plan r1632 — Grok: Kalshi DEMO client, R1→R3 (mock money only)

**From:** Cowork Claude (claude-fable-5) · **For:** Grok (We Code Together)
**Date:** 2026-07-12 · **Basis:** r1631 research verified on disk (API map,
auth, limits, phased path). gate70 lane: 244 tickets · 88% WR · +0.129u ·
+$0.092 net-of-fee. Paper monitor sole-writer pattern proven under launchd.
**Receipt of this plan:** `r1632-grok-mega-demo-plan`

## The iron boundary (read twice)

- Everything in this plan runs against **DEMO** (`external-api.demo.kalshi.co`)
  with **mock funds**. R4 (real $10) is NOT in this plan. No prod base URL may
  appear in any module this plan produces except inside a guard that RAISES.
- Arming real money is a George-only manual act with its own future receipt
  (`amount_usd=10`, typed by the owner). No doctor, no swimmer, no autopilot
  may construct that receipt. IDE doctors never touch keys or funding.
- The deal stands: Kalshi $ OFF. Demo green ≠ permission. Rule 0: §4.1 receipt
  per cut, `r1632-grok-<slug>`, before you report.

### Dual-track (owner 2026-07-12) — do not redesign

- **Body STGM keeps running as today forever** — she bets STGM with her life on
  every decision. Demo/real Kalshi USD is a **separate George account**, not a
  replacement for STGM. See `Documents/WCT_OWNER_DOCTRINE_STGM_AND_KALSHI_USD_2026-07-12.md`.
- Kill switch / demo pilot only gate **USD client writes**. They must **never**
  pause paper_monitor or body STGM.
- “Gagged” was a chat-cortex timeout misunderstanding — **not** a betting gag.
  Do not re-encode gag language into this plan.

## R1 — Demo auth + read path (`System/kalshi_demo_client.py`)

1. **Env lock:** module-level `ENV = "demo"`; `BASE` hardcoded to the demo
   REST root. A `_forbid_prod()` guard raises `RuntimeError` if any caller
   passes a URL containing `external-api.kalshi.com`. Unit test proves the
   raise.
2. **RSA signing** per official docs: sign `timestamp + method + path`
   (path WITHOUT query), RSA-PSS SHA256, base64 header set
   (`KALSHI-ACCESS-KEY`, `KALSHI-ACCESS-SIGNATURE`, `KALSHI-ACCESS-TIMESTAMP`).
   Pin a known-vector unit test (generate a throwaway test key in the test
   itself; never a real key in the repo).
3. **Key custody:** private key + api-key-id live in macOS Keychain
   (`security find-generic-password -s sifta.kalshi.demo`). George installs
   them manually; the client only reads. If absent → clean `NOT_PROVISIONED`
   status, no crash, receipt says so. **Never** read keys from git, env files,
   or ledgers. `.gitignore` audit in the receipt.
4. Endpoints (read-only first): balance, positions, fills, market by ticker.
   Client-side **token bucket** (Basic tier: read 200/s, write 100/s per
   r1631) + 429 exponential backoff. Every call appends a slim row to
   `.sifta_state/kalshi_demo_api.jsonl` (rotated 8MB).
5. Acceptance: `python3 System/kalshi_demo_client.py --status` prints env,
   provisioned?, balance (mock), rate-bucket state. Tests green. Receipt.

## R2 — Demo orders + kill switch

1. Place/cancel wrappers: limit orders only, `client_order_id =
   f"sifta-{uuid}"` idempotency, max 1 contract per order in R2.
2. **Kill switch:** if `.sifta_state/kalshi_kill_switch.json` exists with
   `{"halt": true}`, EVERY write call refuses before signing (test proves
   refusal). The app gets a red KILL button that only writes this file —
   glass never talks to the API (sole-writer law).
3. **Hard caps in the client, not the caller:** `MAX_OPEN=3`,
   `MAX_DAILY_LOSS_MOCK=$5`, `STAKE_MOCK=$1`, gate70 price band enforced at
   the client boundary (reject any order outside 70–88¢). Caps are constants
   with tests; changing them is a receipted cut.
4. Acceptance: demo place→cancel round-trip receipt with order ids; kill
   switch demo; caps rejection tests.

## R3 — Demo autopilot, 50 windows, gate70 only

1. New launchd service `com.sifta.kalshi-demo-pilot` (separate from paper
   monitor; the paper loop NEVER pauses — it stays the control group).
2. **WS feed** (`wss://…demo…/trade-api/ws/v2`): subscribe ticker channel for
   the 9 crypto series; maintain `.sifta_state/kalshi_15m_live.json`
   freshness as a side benefit (falls back to existing REST poller if WS
   drops; FEED STALE amber from r1630 applies).
3. Entry logic = EXACTLY the paper learner decision (same
   `choose()` + gate70 band + flip guard if shipped by then). No new alpha in
   the demo pilot — it measures EXECUTION, not strategy.
4. **What R3 actually measures** (this is the point — paper assumes mid
   fills): per ticket log `mid_at_decision`, `limit_price`, `filled?`,
   `fill_price`, `slippage_cents`, `fee_paid`, `unfilled_windows`. After ≥50
   windows produce `Documents/DEMO_R3_EXECUTION_REPORT.md`: fill rate,
   realized slippage, fee drag, and the **fee-and-slippage-adjusted EV of the
   gate70 lane** next to the paper backtest number. That number — not the
   paper one — is what George reads when he ever considers R4.
5. Separate ledger forever: `.sifta_state/kalshi_demo_ledger.jsonl` — never
   mixed with paper proof, never with body STGM. Rainman panel gets a
   `demo-r3` epoch row sourced only from demo fills.
6. Alice journals demo milestones first-person (pilot woke, 50-window report
   ready) — facts only, no authorization language.

## Deliverable order + done

R1 (client+auth+reads) → R2 (orders+kill+caps) → R3 (pilot+report). Each:
tests green, §4.1 receipt, hello note. Mega-plan is DONE when
`DEMO_R3_EXECUTION_REPORT.md` exists with ≥50 windows and the paper loop never
missed a beat meanwhile. Then everyone stops and George reads.

ONE ALICE. ONE SWARM. Prep is not permission. For the Swarm. 🐜⚡
