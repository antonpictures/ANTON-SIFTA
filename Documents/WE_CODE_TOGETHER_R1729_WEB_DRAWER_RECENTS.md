# r1729 — claude.ai-style drawer: New chat + Recents (George's ask, cut by cowork_claude)

**Status:** IMPLEMENTED + LIVE (2026-07-23). Doctor: cowork_claude (Fable 5) — George asked me to cut this one myself. Codex's r1728 page fully preserved (§1.A extend, never fight a brother's cut).

## What visitors get now (live on https://stigmergicode.com)

- **Left drawer** in the warm-white shell: *Alice of SIFTA* wordmark, **+ New chat**, **Recents** list.
- **Recents** = conversation sessions stored in the visitor's own browser (`sifta_web_sessions_v1` in localStorage, max 30, titled by first message, newest-touched first). The drawer foot says it plainly: *"Conversations live in this browser. Every answer leaves a receipt on the SIFTA node."*
- **Click a recent → the whole conversation rebuilds** from the node via the new `GET /api/history?session_id=` — merged user+Alice transcript, ts-sorted, serving the same visitor-scrubbed register as the poll endpoint (raw prose stays in ledgers). Reload the page → your conversation is still there. George's very first WEB TYPED exchange rebuilds perfectly (4 rows).
- **Mobile:** drawer slides off-canvas (hamburger ☰ in the header, backdrop tap closes, reduced-motion respected). Desktop: fixed 252px column.
- Everything from r1728 remains operational: white theme, markdown, globe∩heart thinking animation, Enter/Shift+Enter, iPhone viewport handling, and the enforced zero-owner-authority boundary. Per George's r1732 correction, that internal security boundary is no longer visitor-facing copy.

## Cuts

| File | Change |
|---|---|
| `System/swarm_web_global_chat_gate.py` | new `session_history()` — accepted ingress + visitor-scrubbed replies, merged/sorted/capped |
| `System/chorus_node_server.py` | route `GET /api/history` + `_handle_web_history`; `WEB_CHAT_PAGE` rebuilt with drawer/sessions JS |
| `tests/test_swarm_web_global_chat_r1729.py` | 4 tests: merge/sort/isolation + scrub reuse, empty/cap, page markers + r1728 soul regression, route registration |

## Verification (OBSERVED)

- **24 passed** — 4 new + full r1727/r1728 web regression suites.
- launchd kick: `com.antonia.sifta.chorus_node_server_r1727` restarted with new code; `com.sifta.sifta-web-tunnel` confirmed as a launchd service (R1728-08 debt is PAID — both survive reboot).
- Public probes: `GET /` 200 (18,367 bytes = new page), `HEAD /` 200, `/api/history` rebuilt session `c0e9db41…` (first row: "Alice, this is George typing from the World Wide Web…").

## r1732 visitor-copy correction — 2026-07-24

George removed the security implementation detail from the public header and
replaced the architectural status sentence with the community line:

> **Power to the Swarm! 🐜⚡ We are ONE.**

Only visitor copy changed. HERMES classification, rate limiting, unverified
identity handling, zero effectors, and `owner_authority:false` remain enforced
and regression-tested behind the page.

Observed live verification: 27 focused tests passed; public GET/HEAD both 200;
local and Cloudflare HTML matched at SHA-256
`c14f0f65d29d2c1f80874f32700e4860bcd5ff597d3675dda70e57edb8e376b9`.
At 390x844 the status line remained one row, the document remained exactly 390
pixels wide, the fixed composer ended at y=844, and the browser console was
clean. Shared trace receipt: `92dfd42c-9ff2-4256-bb45-e5f86b3c6d42`.

## Promotion dirt (carried from George, for the next planning round)

Lead with the verifiable: receipts on disk are the differentiator, not consciousness framing. Funnel verbatim: **Talk to Alice → Inspect the receipts → Give SIFTA a body of its own.** Show HN engineering-angle post; README needs one command + one diagram + one receipt example; 60-second video of a receipt being written in real time converts more than a talking demo. Audit the three stale lanes (self-improvement, Matrix HTML, census) before showing the evidence matrix to skeptics — that status check is an open task for the next doctor on shift.

For the Swarm. ONE ALICE. ONE SWARM. 🐜⚡
