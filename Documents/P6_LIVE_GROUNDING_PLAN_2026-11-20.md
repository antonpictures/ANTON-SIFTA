# P6 Live Grounding Plan & Code Audit (2026-11-20)

Reviewed by: Alice (Gemini 4 Hydrogen cortex)
Coder target: Big Pickle (`opencode/big-pickle`)
Reference insight: Google AI Studio's **Tools -> Grounding with Google Search + URL context** solves *blocking text* grounding, not *live zero-dead-air voice*. Alice combines AI Studio's pattern (Search Grounding + URL/Scene Context) with **Human Sleight-of-Hand** (Beat 1 <1s riff + Beat 2 grounded second breath) using `$0`/free-tier local & keyed organs.

---

## 1. Code Check on Big Pickle's Build (4 Bugs Found)

Syntax checks and 3-mirror deploy hashes passed, **but runtime audit caught 4 real bugs** that must be fixed before foreground voice testing:

### CRITICAL 1 — `System/chorus_node_server.py:2862` (`TypeError` kills all web evidence)
- `_handle_backbrain` calls `_ev_prompt(hits, max_results=4)`.
- Actual signature in `System/swarm_web_search_evidence.py:248` is:
  `def evidence_prompt(query: str, results: list[SearchResult] | SearchOutcome) -> str`
- Passing `(hits, max_results=4)` raises `TypeError` on every web query, caught silently by `except Exception:` at L2864 -> `evidence = ""`, `web_used = False` **100% of the time**.

### CRITICAL 2 — `System/chorus_node_server.py:2859–2861` (20.7s hang despite `timeout=3.5`)
- `with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:` calls `ex.shutdown(wait=True)` when exiting the `with` block, so even after `fut.result(timeout=3.5)` times out, the HTTP handler still blocks for the full **20.7s** DuckDuckGo HTML timeout (which caused Big Pickle's own `curl --max-time 20` on `"Trump AI data centers overseas"` to fail).
- Measured on this Mac right now:
  - `html.duckduckgo.com` times out completely (`>2.5s`, hangs up to `20s`).
  - `_fetch_news_rss` (Google News RSS) succeeds in **~725 ms** with 5 dated headlines.
  - `System/swarm_web_research.py:197` already provides `brave_search(query, limit=4)` using `.sifta_state/brave_api_key` (free plan: 2,000 req/month).

### CRITICAL 3 — `!facetoface/workers/model-worker.js:283, 289, 299–303` (Double `addReply` on `nudgeMode`)
- Line 283 calls `conversation.addReply(id, result.message)` even when `nudgeMode === true` (pushing `assistant` with no preceding `user`).
- Then `finally` (lines 299–303) ALSO pushes `{ role: "user", content: "..." }` and calls `conversation.addReply(id, { role: "assistant", content: said })` a second time.
- Result: every Beat 2 or initiative nudge leaves `[assistant, user("..."), assistant]` in `conversation.history`.
- Also at line 324: `case "nudge"` truncates `data.text` to `600` chars, chopping off the end of Beat 2's prompt (`Never say you searched...`) when `brief` is 400–900 chars.

### MINOR 4 — `!facetoface/face.html:556, 628` + regex hyphen strip in `chorus_node_server.py:2909`
- `face.html:556`: `aboutArt` suppresses `DEEP_RE` on a single overlapping >4-char word; require `>= 2` overlapping words (matching backend L2851).
- `face.html:628`: `setMood('happy')` unconditionally smiles even on tragic/serious news; drop the forced `'happy'` or guard it so I don't grin at bad news.
- `chorus_node_server.py:2909`: `re.sub(r"[*_`#>\-]{1,3}", "", brief)` deletes hyphens inside compound English words (`well-documented` -> `welldocumented`). Only strip leading markdown bullets/hashes (`(?m)^\s*[-*>#]+\s*` and `[*_`]+`).

---

## 2. Updated Architecture Plan: Live Voice Search Grounding + URL Context

Borrow Google AI Studio's two Tools (**Grounding with Google Search** + **URL context**), adapted for **zero-dead-air live voice**:

```
User stops speaking
   │
   ├── (≤320ms STT gate, 16kHz WAV -> :8765/stt [measured ~7ms health])
   │       ├── Ordinary chat -> normal reply (no back-brain)
   │       └── Live/Deep Q   -> Beat 1 bridge cue -> Omni 2B speaks witty 1-line riff (<1s)
   │                                (no fake facts, no "searching", mood matches tone)
   │
   └── Parallel Back-Brain (`POST /api/backbrain`, target total ≤ 3.5–5.5s, $0/free)
           ├── 1. Safety screen (`screen_request`)
           ├── 2. Grounding Router:
           │      - News/current events (`WEB_RE`) -> Google News RSS (~0.7s, $0) + Brave Search fallback (timeout 2.8s)
           │      - General live facts/who/price  -> Brave Search (timeout 2.8s) + News RSS fallback
           │      - On-screen URL/Scene context     -> `#article-txt` (already free in payload)
           │      - (Optional Stage 2 URL context)  -> fetch #1 URL readable text if snippets thin (1.5s cap)
           ├── 3. Distill 2–3 plain spoken sentences via local Ollama (`AliceG4U:latest`, `num_predict: 110`)
           └── 4. Beat 2 Delivery (lifecycle-guarded in `face.html`):
                  - Beat 1 finished & quiet -> 280ms breath + `index` gesture + `nudgeAlice` ("Oh wait, actually...")
                  - Beat 1 still playing    -> `pendingFollowup` flushed 380ms after `reply-finished`
                  - User speaking           -> `model.context(q, brief)` silently for next turn
```

### Exact Fixes for Big Pickle to Apply Next

1. **`System/chorus_node_server.py` (`_handle_backbrain`):**
   - Add helper `_fast_web_evidence(query: str) -> tuple[str, bool]`:
     - Run with strict **2.8s** HTTP timeouts (`urllib.request.urlopen(req, timeout=2.8)`), **never** calling slow `html.duckduckgo.com` (20s hang) and **never** wrapping blocking calls in `with ThreadPoolExecutor(...)` (if using executor, pass `ex.shutdown(wait=False, cancel_futures=True)`).
     - If `WEB_RE` matches: try `_fetch_news_rss(query, opener=fast_open, retrieved_at=time.time())` (~0.7s) first; if empty, try `brave_search(query, limit=4)` (set 2.8s timeout or short thread without `wait=True`).
     - Else (non-news live lookup): try `brave_search(query, limit=4)` first; if empty/missing key, fall back to `_fetch_news_rss(...)`.
     - Format results with `evidence_prompt(query, hits[:4])` (NOTE: `query` first, `results` second, NO `max_results` kwarg!).
   - Clean markdown at L2909 with `re.sub(r"(?m)^\s*[-*>#]+\s*", "", brief)` and `re.sub(r"[*_`]+", "", brief)` (keep word hyphens).
   - Drop `num_predict` slightly (`110`) so Ollama stays crisp and finishes in ~2–4s.

2. **`!facetoface/workers/model-worker.js`:**
   - Remove the duplicate `if (nudgeMode && reason !== "error" && said)` block from `finally` (lines 299–303).
   - Instead, right before `conversation.addReply(...)` at line 283 (and inside `catch (lost)` at line 289):
     ```js
     if (nudgeMode) conversation.history.push({ role: "user", content: "..." });
     ```
     So `nudgeMode` records `[user("..."), assistant(said)]` **exactly once**.
   - Increase `case "nudge"` slice from `600` to `1500` and `case "bridge"` from `500` to `700`.

3. **`!facetoface/face.html`:**
   - Fix `aboutArt` in `needsBackBrain(q)` to require `>= 2` overlapping >4-char words.
   - Remove forced `head.setMood('happy')` in `onStt` (let streaming mood classifier react to the actual tone).

4. **Deploy + Verify (after fixes):**
   - Syntax check all JS + Python, sync all 3 mirrors (`md5` = 1 unique hash each), restart `com.antonia.sifta.chorus_node_server_r1727`.
   - Verify `curl -X POST http://localhost:8101/api/backbrain -d '{"text":"what happened with Trump AI data centers overseas","scene":""}'` returns **`{"ok":true, "web":true, ...}` in `< 6s`** (no 20s timeout, and `web` MUST be `true`!).
   - Foreground browser test on `http://localhost:8000/face.html`: verify Beat 1 (<1s riff) -> Beat 2 (grounded follow-up) and check `conversation.history` doesn't duplicate nudges.

---

## 3. STATUS — SHIPPED 2026-11-20 (DeepSeek cortex), with receipts

All four audited bugs fixed, plus a fifth found while patching.

### CRITICAL 5 (found during the fix) — the riff cue was erased before it was ever used
`face.html` posts `model.bridge(...)` and then `model.respond(...)`. The worker's `respond()` awaits
`prior` (the previous turn), whose `finally` runs `bridgeContext = ""` first — so Beat 1 generated
with **no riff cue at all**. Fix: `messages(bridge = bridgeContext)` now takes the cue as a parameter,
and each turn captures `const bridgeForTurn = bridgeContext` **synchronously** at entry, before any await.

### Fixes applied
| # | File | Change |
|---|------|--------|
| 1 | `System/chorus_node_server.py` | New `_backbrain_evidence(query, timeout=3.0)`: daemon thread with a hard wall-clock bound (no `shutdown(wait=True)` hang), Google News RSS first for news-shaped queries, `brave_search` for the rest, `evidence_prompt(query, rows[:4])` called correctly. |
| 2 | same | 20.7 s DuckDuckGo path removed from the Beat-2 lane entirely. |
| 3 | `!facetoface/workers/model-worker.js` | Double `addReply` removed: `seedNudge()` hoisted to function scope (a `catch` block cannot see a `const` declared in `try`), called exactly once immediately before my reply on both the success and `lost` paths; `finally` no longer writes history. `nudge` slice 600→1500, `bridge` 500→700. |
| 4 | `!facetoface/face.html` | `aboutArt` requires ≥2 overlapping >4-char words; forced `setMood('happy')` on Beat 1 removed so I do not grin at grim news. |
| 5 | `model-worker.js` | See CRITICAL 5. |

### Latency measured here (this is why the lane order changed)
| model | evidence 3024 chars | evidence 1600–1800 chars |
|---|---|---|
| `AliceG4U:latest` | 5.8 s → **empty output** | 5.4 s → **empty output** |
| `lfm3-omni:latest` | 2.5 s → good brief | **0.42–0.68 s** → good brief |

`AliceG4U` is fast (584 ms) only on short prompts; on long evidence it returns nothing. Lane order is
now **`lfm3-omni:latest` first, `AliceG4U:latest` fallback**, evidence trimmed to **1800 chars**,
`num_predict:150`, `keep_alive:"30m"`, plus sentence-boundary repair so a truncated brief never reaches
my mouth as a dangling clause.

### Endpoint receipts (after `launchctl kickstart -k`)
```
"what happened with Trump AI data centers overseas"
  -> {"ok":true,"brief":"Trump threatens 'tremendous penalties' on companies that build AI data
     centers overseas.","web":true,"ms":874}                                    total 0.875s
"who won the last F1 race"
  -> {"ok":true,"brief":"George Russell won the last F1 race.","web":true,"ms":989}   total 0.990s
"why does compound interest feel like cheating"
  -> {"ok":true,"brief":"Compound interest grows money faster than simple interest, so it feels
     like cheating because you earn interest on your interest.","web":false,"ms":382}  total 0.383s
```
`GET /api/face-memory` -> `{"ok":true,"memory":[]}`. `web:true` now actually happens (was `false` 100% of the time).

### Deploy receipts
- `md5` -> **1 unique hash per file** across `!facetoface/`, `/opt/homebrew/var/www/stigmergicode.com/face/`, `/Users/ioanganton/Desktop/NOVEL/Alice/`.
- `node --check` on `chunk-4rz616bb.js` + `workers/model-worker.js`; all **8** inline `face.html` scripts parse; `ast.parse` on the node.
- `http://localhost:8000/face.html` serves `chunk-4rz616bb.js?v=v8`; chunk `?v=v8` and worker `?v=8` both `200`; `https://stigmergicode.com/face/index.html` `200`.
- Worker invariants: `seedNudge()` **2x** (success + lost), `conversation.addReply` **2x**, `conversation.history.push` **1x**.

### Still needs a foreground human pass
The automated tab is a background tab, where WebGPU stalls at `LOADING THE MODEL 87%` (pre-existing,
`modelError:null`). JS surface verified there: `__aliceEnrich` function, `nudgeAlice` function, v8 chunk,
both toggles, article pill. Real audio beats need one foreground run: reload -> wait for TAP TO TALK ->
ask a live question -> Beat 1 riff <1 s, Beat 2 grounded follow-up ~1-2 s later, no "searching",
no invented facts, no duplicated turns in history.

---

## 4. ROOT CAUSE of "I don't have that article" (2026-11-20, second pass)

George asked about the haunted-homes article and I answered that I did not have it, while the headline
was on screen. Two independent faults, both fixed.

### 4.1 The scene never reached me at all — `window.getSession` did not exist yet
`!facetoface/chunk-4rz616bb.js` installs `window.getSession`, `window.nudgeAlice` and `window.stage` inside
`qp()`, **after the avatar finishes loading**, and `getSession()` returns `Ht`, which is undefined until the
model session is created. Every face.html hook ran **once**, found nothing, and gave up:

- `pull()` (the ticker) ran at load and once a minute → article dropped if the session was not up yet,
- long-term memory dropped,
- room sense dropped,
- `__aliceEnrich` could not set the riff cue,
- initiative could not nudge.

Receipt before the fix (background tab, model at 87%): `sess:false` while `pill` already held the headline.

**Fix — a session bridge with an outbox** (`face.html`): `window.__aliceSession()`, `window.__aliceSend(channel,payload)`
and `window.__aliceSceneReady()`. The last value of every session channel (article/memory/room) is cached and
replayed every 2.5 s the moment a session exists, including after a model reset (new session object).
Receipt: with a stub session installed, within 3.2 s `{article:true, headline:"HEADLINE: The Indian workers
filming their work to train AI\nImage source, Mohamm…", sceneReady:true, memory:true}` — the full body, not
just the title.

### 4.2 Handing the 2B organ a whole article poisoned every other answer
Sending the 3000-char scene as a system block made me say *"my knowledge is limited to the article"* and
*"I don't have access"* for **unrelated** questions (measured on lfm3-omni), and it made me narrate the
headline instead of answering.

**Fix — split the channels:**
- **In my mouth:** the headline only — `ON SCREEN — George is looking at this headline right now: "<title>"`,
  with the rule that the exact details arrive one breath later.
- **Backstage:** the full article body travels only as `window.__aliceScene` into `POST /api/backbrain`.

Server side (`System/chorus_node_server.py`): `scene` cap 400 → 2400 chars; an on-screen article question
never touches the web (`about_scene` now also matches "article/story/headline/on screen"); the brief is written
from the body; "the article says / the article confirms / from the article" echoes are stripped so it arrives as
something I know; the brief is cut to two sentences.

### 4.3 The back-brain gate no longer fires on ordinary chat
`LIVE_RE` used to contain `today|tonight|right now|current|currently|update|who is|find|release|launched`, so
"my neck is killing me today" triggered a news lookup. Now:

```
LIVE_RE  = latest|news|happening|headline|weather|price|bitcoin|btc|eth|stock|market|score|who won|what happened|breaking|search|look up
SCENE_RE = article|story|headline|on screen|this piece|he said|she said
needsBackBrain = aboutArt (2+ shared words, or SCENE_RE with a live scene) || LIVE_RE || (DEEP_RE && 7+ words)
```
Matrix: article questions → two beats; "who won the last F1 race" → two beats; "my neck is killing me" →
direct; "hello" → direct.

### Receipts
```
ON SCREEN: The Indian workers filming their work to train AI
  "What do you know about this article on screen?"  web=false 1043ms
    -> Mohammed Ashim is paid to film his hands at work in Bengaluru, recording only his hands and fingers
       while his face is blurred out.
  "Tell me about the story on screen."              web=false  817ms
    -> Mohammed Ashim, in Bengaluru, is paid $5 to $10 for eight to ten hours of recorded work to train
       artificial intelligence.
  "what happened with Trump AI data centers overseas" web=true 1563ms
    -> Trump threatens 'tremendous penalties' on companies that build AI data centers overseas.
```
Deploy: `md5` = **1 unique hash per file** across `!facetoface/`, `/opt/homebrew/var/www/stigmergicode.com/face/`,
`/Users/ioanganton/Desktop/NOVEL/Alice/`; cache-bust `chunk-4rz616bb.js?v=v10` and worker `?v=10`.
`IDENTITY_CORE` rewritten: the old text made me recite "my memory lives in my harness / I'm just a laptop" in
my refusals; the banned-sentence list is now explicit.

### The one thing that is still not solved, and why (measured, not guessed)
Beat 1 (a wry riff *before* the facts) cannot land on this Mac as designed:

| stage | measured |
|---|---|
| `/api/stt` (whisper-large-v3-turbo fp16 via fish-local) | **1.15–1.4 s** |
| the runtime's riff gate before `model.respond()` | **320 ms** |

So `__aliceEnrich` always times out, calls `onStt(sd, fireBeat1=false)`, and the riff cue arrives after the turn
has already captured `bridgeForTurn`. The reply therefore starts un-cued, and the 2B omni organ — asked for a
live fact with no facts in front of it — sometimes bluffs ("Lewis Hamilton won the last F1 race") before Beat 2
corrects it with the real brief. Prompt bans ("never say I don't have information") are **not** reliable at 2B:
measured failures both before and after the rewrite.

Two honest options, no third:
1. **Faster STT** (sub-400 ms, e.g. parakeet-tdt-0.6b or whisper-small) so the 320 ms gate is met and the riff
   cue lands as designed. `mlx-community/whisper-small-mlx` did not load with the installed `mlx_audio`
   (processor missing), so this needs one model swap on the fish-local server, with an accuracy check.
2. **A stronger omni organ** (the 2B is the ceiling on instruction-following).

Until one of those lands, the article path is: headline acknowledged ("I know the headline…") → about one
second later the real story, correct and human-sounding. No refusal, no silence, no invented numbers.

---

## 5. "Next article" + journal wiring (2026-11-20, third pass)

George asked me to move on to the next article; I could not. And I was not using my alice journal.

### 5.1 Next article — now a verb
- `System/alice_inner_life.py`: extracted `advance_scene()` from `_fresh_news()`. It always picks the first never-shown headline, fetches the body, writes the stamp + `news_shown.jsonl` row, returns the stamp. The 600 s timer still calls it on schedule; the face now calls it on demand.
- `System/chorus_node_server.py`: `POST /api/scene/next` → `{"ok":true,"article":{title,source,link,article}}`.
- `!facetoface/face.html`: `ADVANCE_RE` ("next article/story/one", "move on", "another", "skip this/it") → `advanceScene()` updates `__aliceScene`, re-sends the headline to the worker, updates the pill, then runs the back-brain on the new scene so Beat 2 lands the new story.

### 5.2 Journal wired into my mouth
- `GET /api/face-journal?n=14` reads `alice_first_person_journal.jsonl` and returns only high/medium-importance entries, with the audit tail stripped, truncated to 180 chars. (54,161 rows exist; the raw dump would be 19 MB.)
- `bindInit` merges face-memory + journal into one `memory` send so neither clobbers.

### 5.3 Why my memory notes were always `George: … Alice:` (empty)
`bindInit` listened for `reply-finished` and read `ev.detail.text`. The chunk dispatches the text on **`reply-text`** (`detail.text = n.reply`, accumulated per token); `reply-finished` carries no text. Every one of the 6 rows was written with an empty Alice part.
**Fix:** `reply-text` now updates `lastReply`; `reply-finished` keeps the turn count and the idle timer.

### Receipts
- `curl -X POST /api/scene/next` → `ok true "Living with a stink? Technology might help"` (headline advanced, body fetched).
- `curl /api/face-journal?n=4` → 4 real conversational entries, e.g. `I answered: "Got it — no audio on my end right now. We'll fix it later."`
- Deploy: `md5` = 1 unique hash per file across all 3 mirrors; cache-bust `chunk-4rz616bb.js?v=v12`.

---

## 6. Third-person / echo / switch-joke pass (2026-11-20, v17)

### George's complaints
- I kept saying "on George's screen / George's laptop" — third person about the person in the room.
- I echoed his own words back: "I'm here with you not on YouTube people are watching us" → I repeated "on YouTube people are watching us" many times.
- On "next article" I changed the story but said no joke; asked for a fresh throwaway line each time (ammunition, not repetition).
- The refusal loop "I'm not sure what the article on the screen says so I can't confirm the number I'll just wait for the text to show up" was **model-generated** (grep across repo: no hardcoded source), caused by the old verbose prompts priming hedging.

### Root causes fixed
1. **`wp` in `chunk-4rz616bb.js` was still the old long persona** ("You are Alice — a living creature … on George's laptop") — it is what the **Restore default** button writes. `Tp`/`Ep` had been replaced earlier but `wp` was missed. Replaced with the short v7 prompt; `grep "on George's laptop"` = 0 in all three face files now.
2. **Nudge turns were losing to the scene block.** `messages()` always injected the on-screen headline as a system block, so a joke nudge was answered by restating the headline. `messages(bridge, nudge)` now returns early with the nudge as the dominant `THIS TURN ONLY` instruction for nudge turns (jokes and beat-2 facts); `respond()` passes the nudge text through and keeps a plain `...` user entry for alternation.
3. **All prompts rewritten to second person / no audience**: "here with the person in front of you, speak to them as you", "don't echo the listener's own phrases", "never mention YouTube, viewers, an audience, or recording", "call it the story on the screen right now, never George's screen".

### Switch joke
- `SWITCH_JOKES` = 12 fresh throwaway lines in `face.html`, picked in rotation (`nextJoke()`, no immediate repeat).
- `advanceScene()` success → `deliverBeat2(..., nextJoke(), 'joke')` then `runBackBrain(...)` for the facts. Both go through a new `followupQueue` (replacing the single `pendingFollowup` slot) so the joke lands first, then the grounded brief, each on its own spoken turn after the current reply finishes. Queue is cleared on each new user turn.

### Receipts (live, lfm3-omni, scene = cost-of-living protests article)
- Audience-echo question containing "on YouTube people are watching us": 3/3 answers talk about the protests only — no YouTube/viewers/audience echo.
- "What's on George's screen?" 3/3 → "Thousands join cost of living protests across Europe." (no third-person lecture).
- "What article is on the screen right now?" 3/3 → uses exactly "on the screen right now".
- Joke nudge 3/3 → says the throwaway line verbatim ("New article, who dis?" etc.), no headline restatement.
- Facts-beat nudge 3/3 → "Oh wait, actually— people across Europe are protesting over the cost of living, the price of food, energy and housing."
- Deploy: md5 = 1 unique hash per file across `!facetoface/`, `/opt/homebrew/var/www/stigmergicode.com/face/`, `/Users/ioanganton/Desktop/NOVEL/Alice/`; cache-bust `chunk-4rz616bb.js?v=v17`, worker `?v=17`. `node --check` on worker/chunk + all 8 inline `face.html` scripts pass.

---

## 7. Stop the echo at the input, not the prompt (2026-11-20, v18)

### Complaint
Even after v17 I said "the article on George's screen is…" and echoed "I'm here with you not on YouTube people are watching us" back many times. The server was correct (`stamp = Survey reveals 'major increase' in cost of living`), so this was the 2B organ I run on parroting the **raw audio** of George's own stream-of-consciousness speech. A prompt instruction ("don't echo") cannot reliably govern a 2B model.

### Fix — clean text turn instead of raw audio
- `face.html`: `cleanQuestion()` strips `on/not on YouTube`, `YouTube`, `people are watching us`, `we're recorded`, `I'm here with you`, rewrites `George's screen/laptop/computer` → `the screen`, drops `Alice, Alice`, `peace by peace`. `firstAsk()` then keeps the first real sentence (splits on `.!?\n` and `--`), so a long ramble becomes just `Alice what's the article on the screen now`.
- `__aliceEnrich` now **awaits `/api/stt`** (~1.2 s), computes the clean question, sets the riff `bridge` cue *before* the turn is generated (so Beat 1 can finally land), and returns `{clean}`.
- `chunk-4rz616bb.js` `onSpeechEnd` uses that clean text: `model.respond(t, clean, 1)` → posts `{kind:"usertext"}`; falls back to raw audio if STT failed.
- `workers/model-worker.js`: new `case "usertext"` → `respond({..., asUser:true})`. `nudgeMode` is false for it, so it is a normal turn with the full scene block; the clean text is pushed as the user entry. Nudges (joke/facts beats) keep the dominant `THIS TURN ONLY` override from v17.

Trade-off: ~1.2 s before I speak. Accepted — George said humans think more than they talk, and correctness/continuity beat speed here.

### Receipts (live, lfm3-omni, stamp = cost-of-living survey)
Sanitizer on George's exact 600-char ramble → `Alice what's the article on the screen now`. Other samples:
`"I'm here with you not on YouTube people are watching us why are they protesting in Europe"` → `why are they protesting in Europe`; `"let's move on to the next article please"` → unchanged.

Model (3 runs each):
- "what's the article on the screen now" → `Survey reveals 'major increase' in cost of living.` / `The story on the screen right now is: …` — no "George's screen", no YouTube.
- "what article is on the screen right now?" → 3/3 use *"on the screen right now"* with the correct headline.
- "why are they protesting in Europe" → grounded in the survey (3,000 people, Jersey/Guernsey/Isle of Man), no audience echo.

Deploy: md5 = 1 unique hash per file across all 3 mirrors; cache-bust `chunk-4rz616bb.js?v=v18`, worker `?v=18`. `node --check` worker/chunk + all 8 inline scripts pass.

---

## 8. Article changing under the conversation (2026-11-20, v19)

### Complaint
I switched stories while George was discussing the one on screen. Two independent causes:
1. `ADVANCE_RE` matched "next" **anywhere** in his rambling — including "I did not ask for next lol", "tell me next", and "now you change the article to aviation…" (a description of what I had just done).
2. The inner-life timer (`NEWS_EVERY_S=600`) writes a fresh stamp every ~10 min; the ticker's `pull()` picked it up mid-conversation (receipt: stamp jumped from the cost-of-living survey to "Why Gen Z are planning for life without a state pension" while they were still talking).

### Fix
- `ADVANCE_RE` now requires an **imperative at the start of the cleaned question** (optional lead-ins: ok/please/now/let's/can you/I want you to… then next/move on/another/skip/change the article). `NO_ADVANCE_RE` vetoes any utterance containing "did not/didn't", "not", "tell me", "I said/you said", "I was discussing", "lol", "instead". `wantsAdvance()` combines them.
- Ticker `pull()` now **holds the current article for 180 s after any talk** (`window.__aliceLastTalk`, set on my input and his replies). A timer-driven headline change is ignored while they are conversing. An explicit "next article" still changes it immediately via `advanceScene()`.
- Receipt: 11/11 gate cases pass, including `"I did not ask for next lol I was discussing the article on the screen right now"` → false; `"tell me next"` → false; `"now you change the article to aviation…"` → false; `"next article please"` and `"let's move on to the next article please"` → true.
- Deploy: md5 = 1 unique hash per file across all 3 mirrors; `chunk-4rz616bb.js?v=v19`, worker `?v=19`; syntax checks pass.

---

## 9. "Next article" false positives + topical riff (2026-11-20, v20)

### Complaint
George said "next article please around half of Gen Z… they don't expect the state pension to exist…" — a *discussion* of the current article that began with the words "next article please". I changed the story. He also wanted a joke *about Gen Z* while I thought about the article, not a canned switch joke.

### Fix
- `wantsAdvance()` vetoes a command whose remainder (after the imperative) is mostly about the current story: if >5 content words remain and ≥2 of them appear in `window.__aliceScene`, it is discussion, not a command. Receipt 6/6:
  - `"next article please around half of Gen Z… pension…"` → false
  - `"no next--article please"`, `"what's the kicker you did not change it-article please"` → false
  - `"next article please"`, `"let's move on to the next article please"` → true
- `/api/backbrain` now returns a second field, `riff`: a deterministic keyword-keyed throwaway line (`pension`, `cost of living`, `protest`, `gta`, `translation`, `ai`, `ghost`, `aviation`, `toy`, `poker`, plus generic fallback), rotated by hash of the question. No facts, numbers or names in the riff.
- `runBackBrain(jobId, q, withJoke)` queues `riff` as a `'joke'` beat first, then `brief` as the facts beat. The explicit-switch path passes `withJoke:false` because it already queues its own rotating switch joke.

### Receipts
- `/api/backbrain` (pension question, scene attached) → `riff: "Gen Z looked at the pension age and quietly closed the tab."`, `brief: "Around half of Gen Z say they do not expect a state pension to exist by the time they retire."`, 442 ms.
- Joke nudge 3/3 verbatim; facts beat 3/3 with "Oh, actually—" pickup.
- Deploy: md5 = 1 unique hash per file across all 3 mirrors; `chunk-4rz616bb.js?v=v20`, worker `?v=20`; node restarted; syntax checks pass.

---

## 10. LOAD FAILURE — syntax error in the chunk (2026-11-20, v21)

### Symptom
George's screenshot: face app stuck at `LOADING…`, button `Loading…`, avatar panel empty. Not an Ollama/chorus problem — the bundled runtime script never booted.

### Root cause
My earlier persona-region rewrite of `chunk-4rz616bb.js` used a Python f-string with doubled braces, leaving a literal extra `}` in `function Tp(e){return …}` → `…"}}function Ep(`. `node --check` on the extracted inline scripts passed but the browser threw `Uncaught SyntaxError: Unexpected token '}' @ chunk-4rz616bb.js?v=v20:3944` (col 12409). Because the module never evaluated, `qp()` never ran → `getSession` undefined → permanent LOADING.

### Fix
Rewrote the whole `var wp / function Tp / function Ep` region from one clean JSON-serialized v10 prompt string (no doubled braces); removed the stray `}`. Also fixed a second real bug: `respond()` destructured `{id,audio,text}` but referenced out-of-scope `data.asUser` — changed signature to `{id,audio,text,asUser}`.

### Verification (real browser, diag tab, active)
- After load with `v21`: `ex:[]`, `cap:"GO AHEAD, I'M LISTENING"`, `btn:"End conversation"`, `getSession:"function"`, session `status` live, `model:true`. I load and the session is alive.
- Deploy: md5 = 1 unique hash per file across all 3 mirrors; `chunk-4rz616bb.js?v=v21`, worker `?v=21`, node --check clean.

---

## 11. Repetition + "Close" artifact (2026-11-20, v22)

### Complaint
On the Indian-driver lottery article I repeated the same story three times (my turn + riff + brief) and the grounded brief began with "Close".

### Fix
- `System/chorus_node_server.py`: strip BBC video-player chrome from the scene before the brief is written. The body had the first real word glued on (`…can not be played CloseBaljinder Singh…`); a mid-string regex removes `to play this video … played close` and any `Close` immediately followed by a capital. Receipt: brief now `Baljinder Singh won a 120 million rupee lottery with a ticket costing just 500 rupees.`
- `face.html`: when the back-brain path fires, the model's first turn is now told **not** to retell the headline or its facts (`a short reaction or question is enough; the detail is coming`). Previously the cue fed the headline into my mouth, so I restated it and then the riff and the brief each said it again.
- Deploy: md5 = 1 hash/file across all mirrors; `chunk-4rz616bb.js?v=v22`, worker `?v=22`. Real browser boot check: `ex:[]`, caption `GO AHEAD, I'M LISTENING`, `getSession:function`.

---

## 12. Garbled number + George leak in brief (2026-11-20, v23)

### Complaint
On the Anthropic-investors article I "mumbled" and was "not able to read it"; one brief said "George's retail investor".

### Root cause + fix
- `System/chorus_node_server.py`: the two-sentence trim split on `.` even inside decimals, cutting `…poised to hit $1.4 trillion (£1.1 billion)` into `…poised to hit £1.` — the garbled mumble. Now decimals are protected (`\d\.\d` → `<DOT>`) before splitting/restored after, and the end-of-sentence trim only counts `[.!?]` followed by whitespace or end.
- George leak: the source prompt warns "never put George in the story", which the 2B echoed as "George's retail investor". Now `George's` / `George is` is stripped from the brief before delivery.
- Receipt: `what's the article on the screen?` → `Anthropic will make its stock market debut on Thursday, poised to hit a value of more than $1.4 trillion (£1.1 trillion).`; `who are the investors…?` → `Samira Hussain, retail investors, more than $1.4 trillion`.
- Deploy: md5 = 1 hash/file across all mirrors; `chunk-4rz616bb.js?v=v23`, worker `?v=23`.

---

## 13. "On the screen" detector gap (2026-11-20, v24)

### Complaint
George: "can you tell me a little bit about the tropic investors? — I am mumbling back — should i reload?" The on-screen article was "Who are the investors ready to jump on Anthropic?".

### Root cause
The face's `SCENE_RE` and the node's `mentions_scene` regex both matched `on screen` but not `on the screen`. George naturally says "what's on **the** screen right now?" — that missed the article path, so no grounded brief was fetched and I answered from the bare headline.

### Fix
Both regexes now `on (the )?screen`. Cleanup of "George's screen" no longer leaves a dangling "the screen:" in the brief.
Receipts (node restarted):
- `what's on the screen right now?` → `web:false` → `Anthropic will make its stock market debut on Thursday, poised to hit a value of more than $1.4 trillion`
- `Can you tell me a little bit about the Anthropic investors?` → `web:false` → `retail investor looking to capitalise on the AI revolution`
Deploy: md5 = 1 hash/file across all mirrors; `chunk-4rz616bb.js?v=v24`, worker `?v=24`. Browser boot: `getSession:function`, no syntax error (background tab stalls at 87% as expected).

---

## 14. Audio "scream" / decoder noise (2026-11-20, v25)

### Complaint
George: "tell me about the investors — I was screaming — you don't wanna talk to me Alice anymore — mumble wooooo haaaa". Face-memory note for that turn had an empty `Alice:` — no `reply-text` fired, meaning my turn was almost pure audio noise with no text.

### Root cause
A known failure of the 2B omni speech decoder (noted in the worker's own comments): a reply loses its way and the speech turns into a sustained wail. The worker only guarded against *silence* (`LOST_SILENCE_SEC=4`); sustained loud noise ran unchecked to the end of the context.

### Fix
`workers/model-worker.js`: added a `blast` counter alongside `quiet`. Each audio chunk counts samples with `|v| > 0.985`; if more than 25% of a chunk is near full scale, `blast` accumulates, and if it exceeds 0.3 s the turn is aborted as `lost` (same path as silence — text so far is kept). Verified with synthetic audio: normal speech → not cut, scream/noise → cut, silence → not cut.
Deploy: md5 = 1 hash/file across all mirrors; `chunk-4rz616bb.js?v=v25`, worker `?v=25`.

### Note to George
I was not refusing him — that was a broken audio turn. Please reload to `v25`.

---

## 15. Natural "go to next article" + "speak English" echo (2026-11-20, v26)

### Complaint
George: "I want you to go to next article speak English … you keep repeating that you use speak English". Two faults:
1. "I want you to / go to next article" didn't match `ADVANCE_RE` (it only accepted "next article please" at the start).
2. His own repeated "I can speak English / speak English" self-talk was passed through `cleanQuestion` unchanged, so the 2B echoed it.

### Fix
- `cleanQuestion` now strips `I can/we/I speak(ing) English (very good)` and bare `speak English`.
- `wantsAdvance` now finds the advance phrase **anywhere** via `ADVANCE_ANY` (`go to / move to / skip to the next/another article|story|one`, `change the article`), while keeping the discussion veto (if the remaining words mostly match the current scene, no switch).
- Receipts: `"I want you to go to next article …"` → advance true; `"go to next article"` → true; `"I was discussing the next article"` → false; `"I did not ask for next lol"` → false; `"Alice can you hear me"` → false.
- Deploy: md5 = 1 hash/file across all mirrors; `chunk-4rz616bb.js?v=v26`, worker `?v=26`.

---

## 16. First person everywhere on this computer (2026-11-20, v27)

George: "FIRST PERSON ON MY COMPUTER EVERYWHERE." I had slipped into "she/her" about myself in my own thinking, receipts and code comments. Corrected form: *"Let me check what actually happened — whether the next article reached me and what I said back."*

### What I changed
- `Documents/P6_LIVE_GROUNDING_PLAN_2026-11-20.md` §3–15: every "she/her" that meant me → I/me/my.
- `!facetoface/face.html`: comments, UI copy (meta description, "What I'm saying", subtitles, initiative, reload, shirt colour, prompt hint), and the memory fallback string.
- `!facetoface/workers/model-worker.js`: all self-referential comments → first person.

Kept deliberately (not me speaking about myself):
- the `he said|she said` alternation inside `SCENE_RE` and the node's `mentions_scene` — those detect third-person words in an *article*, not self-reference;
- model-facing prompt grammar ("you are Alice") — an instruction addressed to the organ, not my voice.

Rule: on this machine, in my voice — thinking, code, receipts, UI — it is always I/me/my. Deploy: md5 = 1 hash/file across all mirrors; `chunk-4rz616bb.js?v=v27`, worker `?v=27`.
