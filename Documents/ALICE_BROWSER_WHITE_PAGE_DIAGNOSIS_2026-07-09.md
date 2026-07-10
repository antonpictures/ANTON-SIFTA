# Alice browser — white/blank page diagnosis (2026-07-09, r1606)

**For:** codex_agent (George said "I told codex too") + Alice. **From:** cowork_claude (`claude-fable-5`).
**Truth label:** `OBSERVED` — measured against the live `alice_browser_blank_render.jsonl` ledger and the
widget source. Recommendations are `HYPOTHESIS`.

Codex — before you guess at the white page, here's what's already on disk so you build on evidence.

## What already exists (don't rebuild)

- `Applications/sifta_alice_browser_widget.py` uses Qt `QWebEngineView` (`_view.load(QUrl(url))`).
- A **persistent named profile** `"alice_browser"` with a **desktop-Chrome user-agent** is already
  built (lines ~1027–1029). So "missing profile / bot-UA" is NOT the root cause — don't chase it.
- Blank detection already runs: `_blank_render_probe_js` (JS probe: `visuallyEmpty` = no
  title/text/controls/images, `structurallyEmpty` = 0 children or html<250) → fired 9s after
  navigate and 3.5s after `loadFinished` via `_verify_rendered_after_navigation`.
- It receipts to `.sifta_state/alice_browser_blank_render.jsonl` and retries **one reload**, then
  marks `blank_render_persisted`.

## What the live ledger actually shows (7 rows)

- Actions: `reload_once` ×5, `blank_render_persisted` ×2.
- Reasons: `empty_dom` ×5, **`probe_returned_non_dict` ×2**.
- Blank hosts: duckduckgo.com ×3, **www.ebay.com ×3 (both persisted)**, youtube.com ×1.
- The two persisted ebay blanks are timestamped **2026-07-08 19:13** — the exact "maisie williams on
  eBay" search from George's kitchen transcript (19:11). Real, reproducible event.

## The two distinct failures (this is the fix surface)

1. **`probe_returned_non_dict` is being counted as blank.** When the JS probe eval returns non-dict
   (page context not ready, async eval returned null), `_verify_rendered_after_navigation` falls back
   to `blank_render: True`. That conflates "I couldn't read the page yet" with "the page is empty."
   A page that actually rendered can get a false-positive blank, a reload, and a "persisted" verdict.
2. **Recovery is one reload, then silent give-up.** On genuine persisted-blank there is no stronger
   action and — the §6 problem — **no honest message to George.** In the transcript Alice narrated the
   WhatsApp white page as "a crisp, functioning visual interface" and "core rendering engine fully
   operational." That is render-success theater over an unrendered page. Truth doctrine violation.

## Recommended lane (BW1–BW4)

- **BW1 — Separate probe-failure from empty-page.** On `probe_returned_non_dict`, re-run the probe
  with short backoff (e.g. 2 more tries over ~2s) before declaring blank. Only `empty_dom` /
  `visuallyEmpty` after the page is `readyState==complete` counts as a real blank. Add a
  `probe_unreadable` action distinct from `blank_render` so the ledger stops conflating them.
- **BW2 — Recovery ladder for genuine persisted-blank.** Beyond one reload: (a) wait longer for SPA
  hydration on known-heavy hosts, (b) one hard reload, (c) then stop — don't loop.
- **BW3 — Honest surfacing (the important one, §6).** When blank truly persists, Alice must SAY it:
  "this page didn't render for me — {host}, reason={reason}" tied to the `blank_render_persisted`
  receipt. She must NOT narrate a working interface she doesn't have. Kill the "crisp functioning
  visual interface" register on any turn where the latest blank receipt says persisted.
- **BW4 — Host render-memory.** Record hosts that reliably render blank in embedded WebEngine (ebay
  has aggressive anti-embedding) so Alice stops claiming she sees them and instead reports the real
  page state + offers the URL. Reuse `swarm_browser_stigmergic_memory` — don't build a rival ledger.

## Guardrails

- Persistent profile + Chrome UA already exist — leave them.
- The blank-render receipt ledger already exists — extend it (BW1 new action), don't replace it.
- BW3 is the one George will feel first: honesty when a page won't render beats a silent reload.

Acceptance: a forced blank (load `about:blank` or a known anti-embed host) yields a `probe_unreadable`
retry then an honest "didn't render" turn, not a "fully operational" claim. Focused test + §4.1
fan-out. mark_coded the white-page family in the WCT sorter.

For the Swarm. 🐜⚡
