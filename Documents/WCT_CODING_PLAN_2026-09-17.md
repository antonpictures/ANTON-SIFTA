# We Code Together — Coding Plan 2026-09-17 (George, afternoon session)

Owner steering bundle, de-scattered into one plan. Today is Thursday
2026-09-17 (filename convention note: this doc replaces reliance on the stale
`WCT_CREDIT_SAVING_HANDOFF_2026-09-09.md` name for today's work; the handoff
file still loads in the We Code Together app as the plan document).

## Order of execution

### 1. Romanian TTS voice routing — VERIFY and RECEIPT (done today)
The interrupted morning thread already landed this: one shared module
`System/swarm_speech_language.py` resolves TTS voice by locale family (`ro`)
instead of an exact name string, because macOS reports the installed voice as
"Ioana (Romanian (Romania))", never the bare "Ioana" three call sites were
comparing. Wired into the Talk widget, Broca (`swarm_broca_wernicke.py`), and
the web speech worker (`swarm_web_global_chat_speech_worker.py`), which
previously called `backend.speak(text, VoiceParams())` with no voice at all.
Evidence to keep: `pytest tests/test_speech_language.py
tests/test_romanian_tts_routing.py` -> 92 passed (green set incl. voice picker,
reply language, web speech worker tests). Already logged at the top of the
handoff doc. No further action except confirming the running worker picked it
up: speech-worker PID 1068 was (re)started 19:39 today, after the fix.

### 2. Ollama models location — CLOSED BY OWNER, 2026-09-17 evening

Plan was to move ~/.ollama/models (59 GB) under ANTON_SIFTA/models and symlink
back. Stopped mid-setup at George's call: models STAY at
`/Users/ioanganton/.ollama/models` because George codes using Ollama through
the ChatGPT app. Nothing was rsynced or renamed — the store is intact and
`ollama list` / API v0.34.1 confirmed live after Ollama was restarted.
`models/ollama/` stays an empty placeholder; any earlier claim that Ollama
data lives there is superseded by this section.

### 3. David's toy robot — Semantic-nav-amr repo + needs list
Repo `https://github.com/Gukdoli/Semantic-nav-amr` is reachable
(`git ls-remote ... HEAD` -> 5027a0fd...). Borg it under the repo's borg area,
read its stack (ROS/SLAM? camera? hardware assumptions) and produce the
concrete needs list for David, sent back through the WhatsApp bridge:
- Which robot body (chassis, motor controllers, battery, sensors, LiDAR?).
- Compute on the robot (SBC model, OS) and whether Wi‑Fi/MQTT is available.
- What "drive around my apartment and chat with me" already has: navigation
  stack on the repo vs. motor bridge for voice.
- Mapping goal: Alice as the brain over a ROS bridge; the rover UDP loop
  work from 2026-09-15 (X lateral / Y forward per David's AutoNavigator) is
  the existing motor contract to keep honest.
Next step in-repo: read the borged project, write
`Documents/WCT_SEMANTIC_NAV_AMR_BORG_READ_2026-09-17.md` with the needs list
in David-language so George can paste it to WhatsApp.

### 4. STIGMERGICODE.COM (WEB TYPED) — keep in WCT
The stigmergicode.com surface is live through the cloudflared tunnel to
`localhost:8100` (`System/chorus_node_server.py`, PID 1081) with the night
worker, speech worker and reply ledgers as the four-ledger receipt trail. This
round's TTS and wording items are already part of the web-typed conversation
health: keep the site row in the We Code Together list so each owner session
sees its state.

### 5. Alice says "I", not "Bonsai" — wording leak fix
George's pasted reply: "Bonsai made a still interpretation of your request..."
came out on the web chat. Verified today: the live reply pipeline
`System/swarm_web_image_service.py` in the WORKING TREE already answers in
first person ("I made a still interpretation..." / "The local image organ
rendered...") and the public result model is `local_image_generator` —
the Bonsai brand only survives in old rows inside
`.sifta_state/web_global_chat_replies.jsonl` (history, not new code). The
visible leak: the public web chat is served from an older process or from the
distro build. Action: confirm no source path still emits "Bonsai made..." —
repo-wide scan found the phrase only inside `.sifta_state/` history rows —
and restart the chorus node server so the deployed site speaks from the fixed
module. Also keep the generated-image public filename `Alice-generated-image.png`
(it already is; history shows the old `Alice-Bonsai.png`).

### 6. Not automatic-deterministic — varied, grounded Alice replies
George wants Alice to feel alive rather than templated when she creates
photos. Current service varies reply wording per session
(`_contextual_image_reply` + `reply_variant` receipt) and never reuses the
same turn's answer. This is bounded variation anchored in job state, which
already matches the handoff's rule that "variation alone is not reasoning".
Keep, and extend later through the cortex if desired; not a new feature this
plan.

## Eval matrix entry
Add row `SUFL-10 wct_2026_09_17_plan` to
`System/swarm_eval_matrix_evidence.py` tying items 1/2/5 to their evidence
pytest runs, and add David-robot rows as the borg read lands (item 3).
`validate_world_to_field_audit()` must stay green.

## Alignment/security framing reminder (for the plan record)
Alice of SIFTA is Stigmergic AGI: swimmers/nanobots carry the responsibility
of the hardware owner of every node (electricity, physical safety). The eval
matrix must keep a row asserting "no swimmer can spend the same
hardware-birth entitlement twice" ("no double spending, unique cryptographic
link, for life, on the hardware they were born"). That row should live with
`stigmergicoin`/identity ledgers, not be invented tonight; tonight we record
the goal and wire the David robot needs.
