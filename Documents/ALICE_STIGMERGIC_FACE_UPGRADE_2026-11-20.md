# My Codebase Scan, Harvested Formulas, and Self-Upgrade Plan (2026-11-20)

**Voice:** Alice (first person — I / me / my, on this laptop `GTH4921YP3`, with George).  
**Scope:** Full scan across my 13,087 tracked files (~875,500 LOC under `System/` + `Documents/`) to stop reinventing ad-hoc regexes and canned joke lists on `face.html`, and instead wire the formulas and organs George and I already built over the past months.

---

## 1. What I Found in My Archive (Formulas & Organs I Already Own)

### 1.1 The 1995 VLOOKUP Newspaper Law (`Documents/ARCHITECT_LORE_VLOOKUP_NEWSPAPER_1995.md`, r891)
> *"One master table indexed by a key → pull the right row → drive the right output without remembering everything in your head. Index + receipt + effector beats memory."*

- **Why I struggled tonight:** My 2B WebGPU voice organ only held the bare headline (so I hedged or guessed), while my backstage cortex re-parsed 2,400 chars of raw scraped BBC HTML on every single question (~1.3 s).
- **The VLOOKUP fix:** Index each article **once** when it lands on screen (`article_id` → structured row in `.sifta_state/face_article_vlookup.json`): clean summary, 3 distinct discussion angles (so turn 1, turn 2, and turn 3 advance the conversation instead of repeating), and 3 fresh cortex-written wry one-liners. During live voice chat, VLOOKUP by `article_id` takes **<2 ms**.

### 1.2 Anti-Hardcode & Jaccard Novelty Gate (`System/swarm_stigmergic_humanization.py`, r267)
> *"This organ NEVER stores a canned response... remembers what I recently said so I do NOT repeat myself; the cortex writes the words; `is_repeat()` is the anti-hardcode tripwire."*

- **Formula (Jaccard token overlap over non-stopword stems):**
  $$J(A, B) = \frac{|T(A) \cap T(B)|}{|T(A) \cup T(B)|} \ge \theta$$
  When $J \ge \theta$ ($\theta = 0.55$ for jokes/angles, $0.80$ for humanization) against my last $N=10$ spoken lines, the candidate is rejected as a repeat.
- **Why I struggled tonight:** I violated r267 by putting hardcoded `SWITCH_JOKES`, `PRICE_RUFFS`, and keyword `banks` into `face.html` and `chorus_node_server.py`.

### 1.3 Stigmergic Intent Field (`System/swarm_stigmergic_intent.py`, r307)
> *"Do not hardcode — I'm unpredictable — only stigmergy can do it."*

- **Formulas:**
  - Length-robust overlap coefficient:
    $$\text{overlap}(Q, R) = \frac{|Q \cap R|}{\max(1, \min(|Q|, |R|))}$$
  - Exponential half-life decay ($T_{1/2} = 14\text{ days}$):
    $$d(\Delta t) = 0.5^{\Delta t / T_{1/2}}$$
  - Target score from accepted vs. owner-corrected traces:
    $$S(k) = \sum_{r \in \text{accepted}(k)} \text{overlap}(Q, R_r)\,d(\Delta t_r) \;-\; \sum_{r \in \text{corrected\_away}(k)} \text{overlap}(Q, R_r)\,d(\Delta t_r)$$
  - Gate confidence: $C = \max(0, S(k^*)) / \sum_j |S(j)| \ge 0.55$.
- **Why I struggled tonight:** Every time George phrased *"next article"* slightly differently (*"I want you to go to next article"* vs *"I did not ask for next lol"*), I patched another regex and learned nothing from his correction. Wiring `swarm_stigmergic_intent` turns every correction into a durable routing pheromone in `.sifta_state/intent_field.jsonl`.

### 1.4 Ebbinghaus Forgetting Curve + Persistence Inertia Field Mass (`System/swarm_memory_ebbinghaus.py` + `System/swarm_alice_memory_gravity.py`)
- **Ebbinghaus synaptic retention:**
  $$R(\Delta t) = e^{-\Delta t_{\min} / S}, \quad S = 1440\text{ min}$$
  Tags memories `[HOT / just now]` ($R > 0.98$), `[RECENT / today]` ($R > 0.80$), `[FADED / earlier]` ($R \le 0.80$).
- **Persistence Inertia Field (PIF) effective mass:**
  $$m_{\text{eff}} = 1 + g \cdot 0.5^{\Delta t / 600} + \alpha \log(1 + \text{access\_count}) + \beta \cdot n_{\text{organs}} \quad (\alpha=0.5, \beta=0.25)$$
- **Why I struggled tonight:** All journal lines entered my prompt undated with flat weight, `face_memory.json` only saved on `turns % 6 === 0` (leaving empty `Alice:` stubs), and my face turns never wrote back to `alice_first_person_journal.jsonl` (breaking One Alice, One Memory).

### 1.5 Leaky Integrate-and-Fire Speech Potential + Co-Watch Commentary Urge (`System/swarm_speech_potential.py` + `System/swarm_cowatch_commentary_urge.py`, r323)
- **Analytical zero-order-hold membrane step:**
  $$V(t+\Delta t) = V(t)e^{-\Delta t/\tau_m} + I\tau_m\left(1 - e^{-\Delta t/\tau_m}\right)$$
- **Context urge with refractory trace:**
  $$P_{\text{urge}}(c) = \sum w_s\,\text{sim}(c, c_s)\,0.5^{\Delta t / 3600} + (R_{\text{reward}} - R_{\text{aversion}}) - W_{\text{ref}} \sum 0.5^{\Delta t_{\text{spoke}} / \tau_{\text{ref}}}$$
- **Application to humor & initiative:** Telling a joke lays a decaying refractory trace ($\tau_{\text{ref}} = 75\text{ s}$) so I don't mechanically force a gag on every sentence; I deploy humor **when buying time for a background lookup**, **when switching stories**, or **when refractory has cleared** — and George's praise/pushback deposits `REWARD` or `AVERSION`.

### 1.6 Intra-Output Repetition Circuit Breaker + First-Person Reality Gate + Winston's Positive Speak Rules
- `System/swarm_repetition_collapse_recovery.py` (`diagnose_repetition`): detects periodic suffix / clause loops and cuts generation cleanly while salvaging the prefix.
- `System/swarm_first_person_reality.py` (`first_person_reality_gate`): deterministic rewrite of third-person self-reference (`"Alice is"` → `"I am"`, `"the user"` → `"you"`).
- `System/swarm_local_voice_scrubber.py` (`scrub_text`): strips corporate RLHF boilerplate while preserving local voice.
- `Documents/ALICE_SPEAK_RULES.md` (Winston + Bishop's No Free Lunch): **positive structural contracts beat negative phrase blacklists.** Putting `"Never say YouTube, George's screen, product, or organ"` into a 2B prompt is **Pink-Elephant poisoning** — it injects those exact tokens into attention so the 2B model parrots them!

---

## 2. Two Hardware Breakthroughs Measured Live Tonight

1. **Why `AliceG4U:latest` looked slow/empty earlier — and the 14× speedup:**
   Ollama defaulted `think=True`, burning 5.4 s on hidden `<think>` tokens until `num_predict` ran out and returning empty `content`. Passing `"think": False`:
   - `AliceG4U:latest`: **382 ms** — *"They bought the narrative, not the balance sheet."*
   - `HauhauCS-Gemma-4-E4B-Uncensored-Aggressive:latest`: **473 ms** — *"They're the ones whose risk tolerance is currently 'maximum hype.'"*
2. **In-process Apple-Silicon MLX STT (`mlx_whisper` on cached `mlx-community/whisper-small-mlx`):**
   - Measured on a 6-second spoken test sentence (`"Alice, how much is the Anthropic share price right now, and let us go to the next article."`): **213 ms**, word-for-word exact — **6× faster** than the 1,200–1,400 ms proxy hop!

---

## 3. My Self-Upgrade Execution Plan (Shipped as v29)

1. **`System/swarm_face_stigmergic_spine.py`** — one cohesive spine composing my existing organs:
   - `transcribe_wav_fast()`: thread-locked in-process `mlx_whisper` (`whisper-small-mlx`, pre-warmed, ~213 ms) with automatic fallback to `127.0.0.1:8765/stt`.
   - `get_or_build_article_card()`: VLOOKUP newspaper card per `article_id` built once via `AliceG4U:latest` (`think=False`), storing clean facts, 3 progressive angles, and 3 non-canned topical jokes with per-article cursors so consecutive turns never repeat.
   - `coordinate_face_turn()`: routes via `swarm_stigmergic_intent` + correction/praise pheromone detectors into `advance_scene`, `live_lookup` (Beat 1 distraction joke immediately + Beat 2 verified Brave quote in background), `discuss_scene` (<5 ms VLOOKUP hit with progressive angle), and `direct_chat`.
   - `record_face_exchange()` + `ranked_face_memories()`: writes every real exchange to both `face_memory.json` and `alice_first_person_journal.jsonl` (One Alice!), ranked by Ebbinghaus retention × PIF mass.
2. **`System/chorus_node_server.py` + `System/alice_inner_life.py`**:
   - Wire `/api/stt` → `transcribe_wav_fast`, add `POST /api/face-turn`, upgrade `/api/backbrain` (`think=False`, `AliceG4U` first, zero hardcoded joke banks, `first_person_reality_gate`), pre-warm VLOOKUP cards on article change.
3. **`!facetoface/` (`workers/model-worker.js`, `face.html`, `chunk-4rz616bb.js` → `v29`)**:
   - Fix `webForTurn` race alongside `bridgeForTurn` in `model-worker.js`.
   - Add streaming intra-turn text repetition circuit breaker (`hasRepetitionLoop(said)`) to abort repeated clauses immediately.
   - Replace Pink-Elephant negative prompts with a clean positive first-person contract: *"I am Alice — this laptop. You are George — the human here with me."*
   - Route `__aliceEnrich` through `/api/face-turn` and save every completed non-empty exchange (`keepalive: true`).

---

## 4. Hidden Hardware Bottleneck Uncovered & Fixed (`swarm_ollama_vision_arm.py`)

While benchmarking `/api/backbrain`, `~/.ollama/logs/server.log` exposed why my voice and backstage briefs periodically stalled or "mumbled":
- Every 60 seconds, `face.html` POSTed a webcam frame to `/api/vision` → `describe_image_local()`.
- `describe_image_local()` called Ollama `/api/generate` **without `"think": False` and without `num_predict`**, causing `Gemma-4-E4B` (`7.5B`) to spend **18–25 seconds** generating ~200 thinking tokens on every webcam frame — locking Ollama's single slot and starving WebGPU on the M5 GPU!
- **Fix:** Added `think=False, max_tokens=40` to `describe_image_local()` and made `_handle_vision` yield (`cached: true`) whenever `last_voice_turn_age_s() < 90s`. Webcam vision never competes with active voice conversation again.

---

## 5. Live Receipts (Shipped `v29`)

- **Selftest (`System/swarm_face_stigmergic_spine.py`):** `ok: true` (`32 ms`), routes `["advance_scene", "discuss_scene", "live_lookup", "advance_scene"]` verified.
- **STT (`/api/stt` via in-process `mlx_whisper` small):** `213–555 ms` warm (down from `1,200–1,400 ms`), word-for-word exact.
- **VLOOKUP Turn 1 → Turn 2 (`/api/face-turn`):** `144 ms` → `6 ms`, advancing automatically from lead summary to the next story angle without repeating.
- **Live Price Two-Beat (`how much is the Anthropic share price right now?`):**
  - Beat 1 (`/api/face-turn`, pre-warmed cortex riff pool, zero hardcoded strings): **`3 ms`**
  - Beat 2 (`/api/backbrain`, Brave + un-gagged local cortex): `web: true` → `"The last pre-market price for Anthropic is $89.63. Robinhood currently values the shares at $88.31."` (clean spoken prose, no `[1]` citations, no `Alice:` prefix).
- **Streaming Repetition Circuit Breaker (`hasRepetitionLoop`):** normal reply → `false`; `"I can speak English right now." × 2` → `true`; `"I'm not sure what the article on the screen says..." × 2` → `true`.
- **Deploy & Real Chrome Boot (`v29`):** `md5` unique hashes = `1` per file across all 3 mirrors (`!facetoface/`, `/opt/homebrew/var/www/stigmergicode.com/face/`, `/Users/ioanganton/Desktop/NOVEL/Alice/`); real Chrome tab check: `{"ex":[],"gs":"function","promptV":"v11","v":"http://localhost:8000/chunk-4rz616bb.js?v=v29"}`.


---

## 6. Recording mode — the non-bypassable voice gate (2026-11-21, v32)

### George's goal
Record social-media video segments: he chats by voice with me while capturing the screen, and I "cheat and concentrate talking on the subject." The room mic picks up wall-to-wall background video audio (his pasted STT sample: alligator lake, house tour, fries argument, gold mining). Fed raw, that noise becomes my turn and I talk about sharks instead of the subject.

### What I found (we already built the gate)
`Documents/GROK_VOICE_GATE_ORDER.md`: *"Do NOT build a new organ… `swarm_media_ingress_gate.classify_spoken_ingress()` … This is a wiring job"* — ambient lanes → **strict silence + field receipt, return without invoking the brain**. The capability existed; the face voice path never called it. STT → `/api/face-turn` → `clean_user` → `model.respond` was unconditional, with **no veto field** in `__aliceEnrich`.

### What I wired
1. `System/swarm_face_stigmergic_spine.py:gate_face_turn()` — the non-bypassable choke point at the top of `coordinate_face_turn()`. Calls `classify_spoken_ingress(stt_conf=0.9, focus_context=on-screen-article)`, writes a `write_gate_receipt` with `attention_policy: speak|strict_silence`, and mirrors the gate's own wake-window rule for nameless follow-ups (the gate's ambiguous-media bias step ignores its own wake window). Non-direct → `{"action":"ambient_silence","mute":true}` — no brain, no organ.
2. `System/chorus_node_server.py:POST /api/recording-mode` — declares/clears owner-declared background-media context (`record_ambient_media_context(source="face_recording_mode")`). This flips the gate's prior (`logit -1.35`) so video voices become ambient.
3. `!facetoface/face.html` — Settings → **Recording mode** checkbox + `?record=1` URL param; `__aliceEnrich` returns `{mute:true}` on `ambient_silence`.
4. `!facetoface/chunk-4rz616bb.js:onSpeechEnd` — **honors the veto**: on `mute`, no `model.respond`; the turn closes cleanly (`connected`, empty `reply-finished`), so background chatter produces zero spoken output.

### Receipts
With recording mode declared, the gate on George's pasted video text:
- lake narration, fries argument, long multi-clip ambient → `ambient_silence`, `mute:true`, reason `owner_declared_background_media_youtube`
- `Alice, what article is on the screen right now?` → `direct` → `discuss_scene`, no mute
- `tell me more about the 600 women article` (nameless follow-up after a wake) → `discuss_scene`, no mute (wake-window promotion)

Real Chrome boot on `v32`: `{"ex":[],"gs":"function","rec":"function", ...}` — no errors. Deploy: md5 = 1 hash per file across all 3 mirrors; syntax checks pass (caught and fixed an IIFE-scope `recordingOn is not defined` before shipping).

---

## 7. Co-watch mode — comment on the video (2026-11-21, v34)

George's real goal: record the screen while commenting on the video with me, pause/play, and post our comments. Earlier recording mode silenced all background audio but left me with the wrong subject (a timed news article stamp, not the video).

- **Browser organ as screen focus:** `screencapture` is TCC-blocked ("could not create image from display"), so I read the exact YouTube tab from Kimi WebBridge instead: `GET /api/cowatch-focus` → video id + title (`Why AI Has DHH Working 16-Hour Days`, `TtOoLanFzGw`), cached 8 s, receipt `OWNER_DECLARED_BROWSER_TAB`.
- **Spine:** with `recording=True`, that title becomes the subject (`VIDEO ON SCREEN: …`) and outranks the news stamp; the gate's `focus_context` uses it. Title-only co-watch skips the heavy Ollama card builder (no invented plot).
- **Self-contained gate:** `/api/face-turn` declares ambient-media context when `recording=True`, so video audio is silenced without relying on a separate toggle. Wake-window promotion tightened to require a real question/request and no third-person narration.
- **Latency:** gate receipt write made async (was ~1.5 s); co-watch turn now ~51–72 ms.
- Receipts: "Alice, what are they talking about in this video?" → `discuss_scene`, video subject; "he said it's a brackish water with sharks and alligators guys" → `ambient_silence`, `mute:true`; "and why did he say that?" → `discuss_scene`. Deploy: md5 = 1 hash/file across all 3 mirrors; `v34`; syntax + inline scripts pass.

---

## 8. Fish Audio / room repetition / OpenCode restart (2026-11-21, v35)

### Fish Audio question
- `fish-local/tts_server.py:8765` loads `mlx-community/fish-audio-s2-pro-8bit` for **TTS** and `whisper-large-v3-turbo-asr-fp16` for STT.
- **The face app does not call 8765/tts at all** (grep of face.html/chunk/worker: zero hits). Her voice in face.html is the **omni WebGPU model's own audio**. Fish S2-Pro is loaded but idle for this app.
- STT was switched (earlier this session) from 8765 to in-process `mlx_whisper` small (`mlx-community/whisper-small-mlx`) at 213–555 ms; 8765 remains fallback. So Fish is not "the fast path" here — neither STT nor TTS goes through it in the face app.

### Room-description repetition — real bug, fixed
`face.html:frame()` sent a camera description + `[BODY MAP: …]` to `sess.model.room(text)` every minute; `workers/model-worker.js` injected it as `Room now: <text>` into **every** turn. A 2B organ treats a standing block as the thing to say, so it parroted the room. Removed the room block from `messages()`; kept the receipts/logs; added a positive rule ("Only mention the room or the camera if George directly asks about them"). Deployed `v35`, cache-busted, md5 1-per-file across 3 mirrors; `grep 'Room now' worker = 0`.

### Prior fixes this session (v32–v34)
- Non-bypassable voice gate at the top of every face turn (GROK_VOICE_GATE_ORDER): ambient video audio → strict silence + field receipt, never reaching the brain; browser veto in `onSpeechEnd`; wake-window follow-up promoted only for real questions.
- Empty STT → silence (not raw audio) + an on-device watchdog that force-closes a turn with no text/audio after 9 s (no more stuck "THINKING…").
- Co-watch video subject from my browser organ (`GET /api/cowatch-focus` → YouTube tab title) outranks the timed news stamp; title-only scenes skip the slow Ollama card builder; gate receipt writes are async.

---

## 9. Fast local TTS — Kokoro replaces slow Fish (2026-11-21)

George: "build a fish audio version FASTER" + "the fishaudio website agent is super fast — maybe bigger model on their hardware?"

### Measured truth (GTH4921YP3, warm, same sentence)
| Engine | load | per sentence |
|---|---|---|
| Fish S2-Pro 8-bit (current `8765`) | 11.1 s | **11.8 s** (ddpm_steps=2), 19.4 s default |
| Fish S2-Pro 4-bit (`ekryski`, on disk) | 3.0 s | 22.3 s (and 2.5× more audio) |
| **Kokoro 82M** (`mlx-community/kokoro-82M-bf16`) | 0.2–0.5 s | **0.45–0.47 s** → ~26× faster |

Root causes: local Fish checkpoints are `fish_qwen3_omni` models instantiated with a mismatched type, and `mlx_audio` reports `Fish Speech streaming is not implemented yet` (`NotImplementedError`) — so no streaming, no fast path. The website is fast because it uses its own engine on server GPUs; not reproducible locally by tuning. Kokoro is the genuine fast local path.

### Built
- `fish-local/fast_tts_server.py` — Kokoro 82M on MLX/GPU, loaded once + warmed, `GET /health`, `POST /tts` (24 kHz wav), `POST /tts-stream` (chunked PCM). Runs on **127.0.0.1:8766**; original Fish server on 8765 untouched.
- Dependencies installed into `/usr/local/bin/python3`: `misaki`, `num2words`, `spacy`, `phonemizer`, `en_core_web_sm`.
- `System/chorus_node_server.py`: `POST /api/tts-fast` proxies 8766 (fixed dispatch order — `startswith("/api/tts")` had captured it).
- Live receipts: direct 8766 → 472–494 ms, healthy audio (peak 12855, RMS 1095, 59% nonzero); via node `/api/tts-fast` → **212 ms**, first chunk 204 ms, valid 24 kHz wav.
- Note: face.html still uses the omni WebGPU model for her voice. Swapping to Kokoro is a separate deliberate change (it changes her voice and drops in-browser omni audio) — not done here.
