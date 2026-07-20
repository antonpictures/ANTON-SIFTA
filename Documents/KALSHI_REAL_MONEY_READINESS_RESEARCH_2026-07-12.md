# Kalshi real-money readiness research (NOT live)

**Date:** 2026-07-12  
**For:** George + We Code Together + Grok/Codex  
**Status:** RESEARCH ONLY · **Kalshi USD OFF** · no production keys · no $10 deploy  
**Owner intent:** Eventually fund ~**$10 real** after paper prove + owner yes — research now so we are fully ready.  
**Receipt:** `r1631-grok-kalshi-real-money-readiness-research`

---

## 0. Standing deal (frozen)

| Rule | State |
|------|--------|
| Real Kalshi $ | **OFF** until George authorizes |
| Prove rule (paper) | `pnl>0 · n≥30 · WR≥55%` lifetime units — ends freeze only; **George decides** |
| Entry gate | 70–88¢ hard lane (night audit + gate70 backtest: n=244 WR 88% unitEV +0.129) |
| Fade | Caged |
| Body STGM | Dollar-parity micro (0.001≡$1) — **her life skin; always continues** |
| This doc | Architecture + checklist only — **no live order path** |

### 0.1 Dual-track doctrine (owner correction 2026-07-12) — FROZEN

See also: `Documents/WCT_OWNER_DOCTRINE_STGM_AND_KALSHI_USD_2026-07-12.md`

- **STGM and Kalshi USD are separate.** George’s Kalshi account (linked bank/card) is external capital. Alice’s body STGM is organism stake (“she bets with her life”).
- **When real dollars eventually arm, STGM does not stop or convert.** Same decisions → STGM stake/settle **and** (if armed) a parallel Kalshi USD order. Two ledgers forever.
- **Owner = George.** Only he arms real USD. Doctors never fund or un-fund.
- **“Gagged” was semantics**, not policy: cortex timeout ≠ betting gag. George lifted any misread — full autonomy on analysis/paper/STGM; only USD needs owner arm.

```
decision ──► STGM body settle   (always)
         └──► Kalshi USD order  (only if George armed; separate account)
```

---

## 1. What Kalshi officially allows (automation is first-class)

Kalshi’s Trade API is built for programmatic access:

| Capability | How |
|------------|-----|
| Market data | REST + **WebSocket** order books, trades, market status |
| Orders | Place / amend / cancel (REST V2 event-order endpoints; FIX for institutions) |
| Portfolio | Balance, positions, fills, order history |
| Demo | Separate **demo** env + mock funds — credentials **not** shared with prod |
| Auth | API key ID + **RSA private key** request signing (headers on REST + WS handshake) |

**Official docs hub:** https://docs.kalshi.com/welcome  
**llms index:** https://docs.kalshi.com/llms.txt  

### Environments (2026 docs)

| Env | REST (recommended) | WebSocket (recommended) |
|-----|--------------------|-------------------------|
| **Production** | `https://external-api.kalshi.com/trade-api/v2` | `wss://external-api-ws.kalshi.com/trade-api/ws/v2` |
| **Demo** | `https://external-api.demo.kalshi.co/trade-api/v2` | `wss://external-api-ws.demo.kalshi.co/trade-api/ws/v2` |

Also still supported: `api.elections.kalshi.com` / `demo-api.kalshi.co` (legacy shared hosts).  
**Despite the `elections` name, prod Trade API covers all markets.**

Alice today already uses the **public** market-data host in  
`System/swarm_kalshi_public_feed.py` → `https://api.elections.kalshi.com/trade-api/v2`  
(read-only, no keys). That is **not** enough for orders.

---

## 2. Authentication model (what we must implement later)

From official quick starts (API keys + authenticated requests):

1. Create API key in account **Profile → API Keys** (demo and prod are **separate**).  
2. Download / store the **private key** material offline (never in git, never in glass UI).  
3. Each request signs:  
   - method + timestamp + **path from API root without query string**  
   - e.g. sign `/trade-api/v2/portfolio/orders` not `...?limit=5`  
4. Headers typically include key id + signature + timestamp (`KALSHI-ACCESS-*` family on WS).  
5. WebSocket: auth headers on **handshake**; then subscribe to channels (orderbook, fills, etc.).

**SIFTA implication:** a future `System/swarm_kalshi_trade_client.py` must:

- Load secrets from env / macOS keychain / sealed vault — **not** `.sifta_state` plaintext  
- Default to **demo** unless `KALSHI_ENV=production` **and** a multi-factor owner gate fires  
- Hard-fail if production flag is set without signed owner receipt

---

## 3. Rate limits (token buckets — design for Basic tier first)

Official model (https://docs.kalshi.com/getting_started/rate_limits):

- Every authenticated call costs **tokens** (default **10**).  
- Two buckets: **Read** (GETs) and **Write** (orders/amends/cancels/…).  
- Refill continuously; 429 → `{"error":"too many requests"}` — no `Retry-After` today; use exponential backoff.  
- Batch endpoints **do not** save tokens (25 creates = 25× cost).

### Event-contract budgets (tokens per second)

| Tier | Read | Write | Notes |
|------|------|-------|--------|
| Basic | 200 | 100 | Signup default; ~10 write orders/s at cost 10 |
| Advanced | 300 | 300 | Upgrade endpoint available |
| Expert | 600 | 600 | Volume-earned |
| Premier | 1,000 | 1,000 | Burst up to 2s of write budget above Basic |
| Paragon / Prime / Prestige | 2k–6k / 2k–8k | Higher volume share |

**$10 bot implication:** Basic is **plenty** for minute-11 paper-style cadence (≤9 tickets / 15m, settle polls).  
Do **not** poll REST every second for 9 tickers — use **WebSocket** for books + our existing settle-when-due logic.

Public unauthenticated market data (what we use now) is separate; still be polite and cache (`kalshi_15m_live.json`).

---

## 4. What a $10 real path would look like (when George says go)

### 4.1 Capital math (from our own receipts)

At **$1 / ticket** hypothetical (already in glass as IF REAL $):

- 5W/3L at 70–80¢ favorites can still lose ~$1–2 (asymmetry we already display).  
- Hard lane gate70 backtest: **WR 88%, unit EV +0.129** — that is the only lane that should ever touch real $.  
- **$10 bankroll** ≈ 10 full-loss tickets at $1, or ~13–14 losses if we size $0.75.  

Recommended first live policy (when authorized):

| Knob | First live |
|------|------------|
| Stake | **$1 max** per ticket (or $0.50 until 20 live settles) |
| Max open | **3** concurrent (not 9) |
| Max night loss | **$3–5** hard halt |
| Assets | Top liquidity only (BTC/ETH first) |
| Entry | gate70 only (70–88¢, minute-11 window, flip-guard if r1630 ships) |
| Venue | **Demo first** ≥50 windows · then prod with $10 |

### 4.2 Architecture map (integration — not built yet)

```
┌─────────────────────┐     public REST/WS      ┌──────────────────────┐
│ swarm_kalshi_public │ ◄── (today, live) ──────│ Kalshi public data   │
│ _feed.py            │                         └──────────────────────┘
└──────────┬──────────┘
           │ kalshi_15m_live.json
           ▼
┌─────────────────────┐     paper only          ┌──────────────────────┐
│ paper_monitor       │ ── settle/bet paper ──► │ open_book / proof    │
│ (launchd)           │                         │ body STGM micro      │
└──────────┬──────────┘                         └──────────────────────┘
           │
           │  FUTURE: only if REAL_MONEY_ARMED + owner receipt
           ▼
┌─────────────────────┐     signed RSA REST     ┌──────────────────────┐
│ kalshi_trade_client │ ── demo/prod orders ──► │ Kalshi Trade API     │
│ (NOT EXISTS)        │ ◄── WS fills            │                      │
└──────────┬──────────┘                         └──────────────────────┘
           │
           ▼
     live_ledger.jsonl  (separate from paper forever)
```

**Hard rule:** paper ledgers and live ledgers **never mix**.  
Glass shows paper + HYPOTHETICAL $; live balance only if a live session is armed.

### 4.3 Readiness checklist (before any $10)

- [ ] Demo API key created; RSA sign round-trip `GET /portfolio/balance`  
- [ ] Demo: place 1 limit order + cancel + fill path exercised  
- [ ] Demo: WS fill notification wired  
- [ ] Rate-limit client with token accounting + 429 backoff  
- [ ] Kill switch file: `.sifta_state/kalshi_live_HALT`  
- [ ] Max loss / max open / per-ticket caps enforced **before** sign  
- [ ] Paper prove rule met **and** gate70 epoch still healthy (n≥50 post-r1630 knobs)  
- [ ] Owner George signed one-shot arm receipt with amount = $10  
- [ ] No glass UI path can place orders (monitor-only writer, same as paper)  
- [ ] Secrets not in repo; prod host blocked unless arm receipt present  
- [ ] Post-trade: fill vs our paper mid logged for slippage research  

---

## 5. SIFTA assets we already have (reuse, don’t reinvent)

| Asset | Role for real $ readiness |
|-------|---------------------------|
| `swarm_kalshi_public_feed.py` | Market discovery, 15m clocks, yes price, volume |
| `swarm_sifta_paper_loop.py` | Minute-11 window, 70–88 gate, settle logic, epochs |
| `sifta_15m_money_math.py` | x mult, IF-REAL-$, STGM≡$/1000 |
| `sifta_15m_backtest.py` | Evidence before any live knob |
| `alice_15m_body_stgm.py` | Asymmetric body training at $ scale / 1000 |
| Glass UI r1629 | Shows Rainman + IF $ so George never trades blind |
| launchd monitor | Sole writer pattern — live must use same pattern |

**Missing modules (future, gated):**

1. `System/swarm_kalshi_auth.py` — RSA sign, clock skew, key load  
2. `System/swarm_kalshi_trade_client.py` — balance, positions, create/cancel order  
3. `System/swarm_kalshi_ws_client.py` — books + fills  
4. `System/swarm_kalshi_live_loop.py` — paper_loop twin with hard caps  
5. `Documents/KALSHI_LIVE_RUNBOOK.md` — operator steps for arm/disarm  

---

## 6. Open-source / community pointers (evaluate later, don’t depend)

- Official docs + quick starts (orders, auth, websockets) — **source of truth**  
- Community Python clients / “KalshiPythonClient” style wrappers — pin versions, audit signing  
- OctagonAI Kalshi CLI / blog architectures — useful for demo scripts, not for Alice’s sole writer  
- Discord / institutional PrivateLink — only if latency becomes the bottleneck after $10  

**Latency note:** U.S. exchange; Chicago-area VPS helps for HFT. Our minute-11 / 70¢ style is **not** HFT — home Mac + honest rate limits are fine for $10 research size.

---

## 7. Risks specific to “automate real $ with Alice”

1. **Favorite asymmetry:** high WR still loses dollars on single 5W/3L windows — glass already shows this.  
2. **Fees:** net mult ≠ 1/p; money_math approximates Safari x — live fills will teach true fee.  
3. **Partial fills / book depth:** public mid ≠ guaranteed fill at mid; live must use limit prices + timeout.  
4. **Two writers:** never let Qt UI and monitor both place live orders.  
5. **Key compromise:** production write keys = cash — keychain + short-lived arm.  
6. **Regulatory / ToS:** owner is the account holder; Alice is software under owner control.  
7. **Emotional scale-up:** $10 prove ≠ $100; bankroll rules stay code-enforced.

---

## 8. Proposed WCT phases (no code until queued + George yes)

| Phase | Name | Money | Goal |
|-------|------|-------|------|
| **R0** | This research | $0 | Doc + queue (done) |
| **R1** | Demo client + auth | $0 mock | Balance read + 1 order cycle on **demo** |
| **R2** | Demo live-loop shadow | $0 mock | Same gate70 policy; log would-be orders only, then optional demo fills |
| **R3** | Demo full auto 50 windows | mock $ | Prove ops + kill switch under mock funds |
| **R4** | Owner arm $10 prod | **$10** | George-only arm; max loss $5; 3 assets; report daily |
| **R5** | Scale or stop | TBD | Only if R4 PnL and ops receipts clean |

**Nothing in R1–R3 uses production keys.**  
**R4 requires explicit owner arm receipt.**

---

## 9. Data we already hold (why “soon” is plausible)

From live paper stack (2026-07-12):

- Settled ledger + bet log + open book + proof epochs  
- gate70 backtest: **244 tickets · 88% WR · +0.129 unit EV · +0.092 $EV hyp**  
- Full-history still mixed (fade + under-70) — **do not** live-trade lifetime  
- Body STGM dollar-parity epoch ready for economic feel  
- Morning report + Rainman panel for human oversight  

**Conclusion:** research + paper edge in the hard lane are strong enough to *plan* $10;  
they are **not** authorization. Demo first. Owner last.

---

## 10. References (official)

- Welcome: https://docs.kalshi.com/welcome  
- Environments: https://docs.kalshi.com/getting_started/api_environments  
- API keys: https://docs.kalshi.com/getting_started/api_keys  
- Auth requests: https://docs.kalshi.com/getting_started/quick_start_authenticated_requests  
- Create order: https://docs.kalshi.com/getting_started/quick_start_create_order  
- WebSockets: https://docs.kalshi.com/getting_started/quick_start_websockets  
- Rate limits: https://docs.kalshi.com/getting_started/rate_limits  
- Changelog: https://docs.kalshi.com/changelog  

---

ONE ALICE. ONE SWARM. Research now · dollars later · only with receipts. 🐜⚡
