# NEON review packet — face app full build (2026-11-20)

Requested by the Architect. Reviewer: NEON. Implementer: the current cortex arm (Flash).
Scope: `http://localhost:8000/face.html`, P0–P5 from the approved plan, plus the public
landing page. Reference implementation: ANTON-SIFTA.

## 1. What changed

### P0 — live bugs (all fixed)
| # | File | Change |
|---|------|--------|
| 1 | `!facetoface/face.html` (~L420–445) | Fixed the `SyntaxError` in the one-time persona script (unescaped `"I'm Alice"`). Added `ava.systemPromptV='v3'` so stale prompts are actually replaced. New prompt: spoken rhythm, opinions, follow-ups, no model names. |
| 2 | `!facetoface/face.html:452` | Typo `stigmergicoin.com` → `stigmergicode.com`. |
| 3 | `!facetoface/face.html:554` | `window.__aliceEnrich` is now non-blocking: returns `Promise.resolve()` immediately so the chunk calls `model.respond` without waiting on STT + web search. Results queue and flush to `model.context` on `reply-finished`. |
| 4 | `!facetoface/chunk-4rz616bb.js` | All **three** built-in default personas still contained `my LFM3-Omni organ, my AliceG4U cortex` — replaced with model-free wording + spoken-rhythm guidance. This was the likely source of her saying "Liquid/LFM" even after the worker was hardened. |

### P1 — living body
`!facetoface/face.html:599`, new *LIVING CREATURE ENGINE*:
- Wires `stage.head` + `getSession()` events:
  - `user-speaking`: `makeEyeContact(4000)` + eye-contact/nod pulse every 2.6–4 s.
  - `processing`: `lookAhead(900)` — thinking reads as a glance away, not a freeze.
  - `ai-speaking`: `makeEyeContact(2600)`.
  - `interrupted`: `setMood('fear', 380)` startle, then neutral.
- Streaming `reply-text` delta classifier maps to TalkingHead moods:
  `love / happy / sad / angry / fear / disgust`, 4.2 s cooldown, decay to neutral 5 s after the reply.
- `requestAnimationFrame` breathing on `Spine2.scale.y` (±0.9%, ~13 breaths/min), no conflict with the body-width slider (which uses X/Z).

### P2 — creature prompting
- `!facetoface/workers/model-worker.js:63`: short spoken turns (1–3 sentences), contractions, small reactions, real tastes and point of view, playful disagreement, a genuine follow-up ~1 turn in 3, never customer-support voice.

### P3 — initiative (she can speak first)
- Worker: new `{kind:"nudge", id, text}` message; `respond()` accepts an injected text user turn; same voice/text/audio pipeline and receipts.
- Chunk: model proxy `nudge()`, `Session.startNudge()` (full turn lifecycle: voice turn, metrics, status), exposed as `window.nudgeAlice(text)`.
- Face: Settings → **Initiative** (default ON). Arrival greeting when room bodies go 0 → ≥1 after 3 min away; one idle nudge after 48–60 s of quiet (max one per 2 min).

### P4 — cross-session memory
- `System/chorus_node_server.py`: `GET/POST /api/face-memory`, backed by `.sifta_state/face_memory.json` (rolling 20 notes, atomic replace).
- Worker: `case "memory"` → `memoryContext` injected into `messages()` with "weave in naturally, never recite".
- Face: loads memory on boot into `sess.model.memory(text)`; saves a compact `George: <last STT question>. Alice: <reply snippet>` every 6 turns and on `beforeunload`.

### P5 — Companion mode
- Face: Settings → **Companion mode** (default OFF, persisted in `ava.layout`). Hides `● LIVE`/`ALICE NEWS` bar, lower-thirds and divider; Alice full-bleed; your camera becomes a 212×142 rounded PiP; current article becomes a collapsible pill at top-right. Studio mode unchanged, one click away.

### Bonus — public landing
- `/opt/homebrew/var/www/stigmergicode.com/index.html` and `!facetoface/index.html`: removed the manifesto/hero/coin/footer text. Now a full-viewport `100dvh` chat iframe to the node — clean Claude.ai-style entry. Verified live at `https://stigmergicode.com/`.

## 2. Verification receipts

- **Syntax:** `node --check` on `chunk-4rz616bb.js`, `workers/model-worker.js`, and all 9 inline `face.html` scripts → all pass. `ast.parse` on `System/chorus_node_server.py` → pass.
- **Deploy integrity:** `md5sum` across the three mirrors
  (`!facetoface/`, `/opt/homebrew/var/www/stigmergicode.com/face/`,
  `/Users/ioanganton/Desktop/NOVEL/Alice/`) → **1 distinct hash per file** for
  `face.html`, `chunk-4rz616bb.js`, `workers/model-worker.js`.
- **Live browser (Kimi WebBridge, test tab closed afterward):**
  - `typeof window.nudgeAlice === 'function'` ✅
  - `window.stage.head` present ✅
  - `ava.systemPromptV === 'v3'`, prompt contains "spoken turns", no `LFM3|Liquid` ✅
  - Settings contain initiative + layout toggles and article pill ✅
  - Companion toggle: body class flips, article pill `display:block`, netbar `display:none`, reverts cleanly ✅
  - Live ticker shows current article: "Robot vessels take on the dangerous work of mine hunting" ✅
  - No JS exception observed; no `modelError` reported.
- **Backend:** after `launchctl kickstart -k gui/501/com.antonia.sifta.chorus_node_server_r1727`:
  - `GET /api/face-memory` → `{"ok":true,"memory":[]}`
  - `POST` smoke note → `{"ok":true,"count":1}`
  - `GET` after → note present; test note then cleared from `face_memory.json`.
- **Rollback:** timestamped backups in `/tmp/face.html.bak.*`, `/tmp/chunk-4rz616bb.js.bak.*`, `/tmp/model-worker.js.bak.*`, `/tmp/chorus_node_server.py.bak.*`; git history in `!facetoface/.git`.

## 3. Known limitation / open item for NEON
- The automated browser test tab is a **background tab**; WebGPU model load stalls at
  "LOADING THE MODEL 87% OF 1.6 GB" there (`ready:null`, `modelError:null`). This stall was
  observed before these changes too. The full nudge → audio round-trip therefore could not
  be exercised headlessly. **Please verify in the foreground tab:** reload, wait for
  "TAP TO TALK", then (a) say something with "haha" → face should brighten; (b) interrupt
  her → startle + eye contact; (c) leave quiet ~50 s → at most one spontaneous remark;
  (d) reload after telling her something personal → she should remember it after 6 turns
  (or after you leave the page).
- If the foreground tab also stalls at 87%, that is a pre-existing WebGPU/model-cache
  issue, not introduced by this build — check the worker's progress events and the
  mmproj URL fetch before touching the new code.

## 4. Suggested review order
1. `face.html` persona script escaping (P0-1) and non-blocking enrich (P0-3).
2. Chunk surgery: `startNudge`, `nudge` proxy, `window.nudgeAlice` (minified but surgical; three exact-match replacements).
3. Worker `respond({id,audio,text})` path — audio turns must be unchanged.
4. `chorus_node_server.py` memory endpoints — input is bounded (800 chars, 20 rows), no auth change, CORS already allowed.
