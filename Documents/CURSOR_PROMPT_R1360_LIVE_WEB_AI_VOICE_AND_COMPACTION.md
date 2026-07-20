# CURSOR_PROMPT - r1360 live web-AI proof, voice loop, and safe compaction

**Receipt id:** `r1360-codex-cursor-live-web-ai-voice-compaction`
**Hand:** Cursor
**Owner command:** `ASSIGN JOBS TO CURSOR`
**Covenant:** `Documents/IDE_BOOT_COVENANT.md`; `AGENTS.md`
**Prime directive:** Do not block Alice. Repair capability; never delete or gate a live organ without proof and receipt.

## Start sequence

Run this first, before claiming a lane:

```bash
cd /Users/ioanganton/Music/ANTON_SIFTA
python3 tools/whats_left.py
tail -100 .sifta_state/ide_stigmergic_trace.jsonl
git status --short
```

Claim exactly one lane at a time. Write a start receipt with a unique id like
`r1360-cursor-lane0-live-proof-start`, then append the close receipt when done.
If another hand is already inside the same files, narrow the lane or yield. Do
not rewrite another doctor's tournament section.

## Lane 0 - Reload proof and live web-AI validation (P0)

Current live list says r1359 fixed named-engine Perplexity routing on disk, but
Alice must reload before the owner can trust it.

Task:

1. Reload Alice or ask George for the reload proof if Cursor cannot control the
   live GUI body.
2. Live-test: `SEARCH ON PERPLEXITY.AI PLS 'lost GIRLFRIEND' ENT`
   - Expected: reply names Perplexity and the browser host is `perplexity.ai`.
   - Failure: any `Default for ON PERPLEXITY.AI` reply is stale or broken.
3. Live-test: `ask Duck.ai what is stigmergy`
   - Expected if no challenge: typing receipt has `type_result.ok=true`, and an
     `answer_captured` row contains answer text that is not just the prompt.
   - Expected if CAPTCHA/verification appears: Alice says the visible challenge
     blocks the AI answer and routes to Perplexity. No fake click success.
4. Live-test: `read the answer`
   - Expected: reads a real captured AI answer only. If blocked or absent, say
     the gap plainly.

Acceptance:

```bash
python3 -m pytest tests/test_web_ai_chat_bridge_r1345.py tests/test_search_provider_reality_r1325.py tests/test_live_probe_fixes_r1339.py -q
python3 -m py_compile Applications/sifta_talk_to_alice_widget.py Applications/sifta_alice_browser_widget.py System/swarm_web_ai_chat_bridge.py
python3 tools/whats_left.py
```

Append a tournament update with the live result. If the result is blocked by
CAPTCHA, mark it `OBSERVED HARD BLOCK`, not failure theater.

## Lane 1 - Voice feedback/drop loop (P0)

The live transcript still flooded: `Voice is dropping a lot right now...` while
Alice was busy and after TTS. Fix the microphone/TTS suppression boundary.

Inspect first:

- `Applications/sifta_talk_to_alice_widget.py`
- `System/audio_ingress.py`
- `System/swarm_keyboard_mic_guard.py`
- `tests/test_alice_parrot_loop.py`
- `tests/test_talk_microphone_rate_fallback.py`
- `tests/test_swarm_keyboard_mic_guard.py`

Task:

- Extend or harden the post-TTS Broca/mic tail with a receipted reason.
- Prevent queued noisy voice clips from generating repeated owner-facing nag
  messages while Alice is already busy.
- Add or update a focused regression test for the repeated drop-message case.

Acceptance:

```bash
python3 -m pytest tests/test_alice_parrot_loop.py tests/test_talk_microphone_rate_fallback.py tests/test_swarm_keyboard_mic_guard.py -q
python3 -m py_compile Applications/sifta_talk_to_alice_widget.py System/audio_ingress.py System/swarm_keyboard_mic_guard.py
python3 tools/whats_left.py
```

## Lane 2 - Provider grammar and recipe context (P0/P1)

The owner uses natural commands like:

- `SEARCH ON DUCK.AI PLS what is stigmergic consciousness`
- `PLS SEARCH FOR THIS RECEPIE ON DUCK.AI`

Task:

- Decide and implement the command grammar so `SEARCH ON DUCK.AI PLS ...` does
  not become `Default for ON DUCK.AI ...`.
- If the target is Duck.ai chat, route through `System/swarm_web_ai_chat_bridge.py`.
- If the target is search results, label it honestly as a DuckDuckGo/search route.
- For `this recipe`, build the query from recent cooking context:
  polenta, hard-boiled eggs smashed with butter, cream cheese/cheese, hot polenta
  poured over the egg-butter mix.

Acceptance:

```bash
python3 -m pytest tests/test_web_ai_chat_bridge_r1345.py tests/test_search_provider_reality_r1325.py tests/test_live_probe_fixes_r1339.py -q
python3 tools/whats_left.py
```

## Lane 3 - Screen-pixel law for `/sc` (P1)

The transcript shows `/sc` answered from stale page context instead of fresh hard
screen pixels. Fresh screenshot pixels must outrank DOM, memory, and prior page
summaries.

Task:

- Find the `/sc` answer composer.
- Add a guard/test so if pixels and stale context disagree, Alice says pixels win
  and reports only what is readable.
- Do not invent page names from stale receipts.

Acceptance:

```bash
python3 -m pytest tests/test_talk_self_screenshot_command.py tests/test_vision_honesty_law.py -q
python3 tools/whats_left.py
```

## Lane 4 - Click/challenge honesty (P1)

The owner said to click the three Duck squares. Alice must not claim success
without body click receipts. If the grid is a CAPTCHA/human verification, do not
automate bypass; report the visible blocker and ask for owner/manual completion.

Task:

- Separate normal clickable UI targets from verification challenges.
- For normal UI: click with per-click receipt and visible coordinates.
- For CAPTCHA/verification: no bypass, no fake completion; write blocker receipt.

Acceptance:

```bash
python3 -m pytest tests/test_captcha_click_r1357.py tests/test_swarm_browser_body_loop_r1338.py -q
python3 tools/whats_left.py
```

## Lane 5 - Safe compaction after live P0s

Use the r1357 compaction assignment after Lane 0/Lane 1 have receipts. Claim one
territory at a time:

- A: `.simulation_publicpush_sandbox` + `.distro_build` mirror-tree quarantine.
- B: root one-off scripts: `patch_*`, `fix_*`, `scratch_*`, `finish_*`, `append_*`.
- C: exact-hash first-party duplicate modules.
- D: dead `old_*`, `orig_*`, `*_backup`, `.bak` first-party files.
- E: tracked `py_compile` perfection sweep.

Guardrails:

- Never touch vendored third-party duplicates.
- Never delete a wired organ.
- Every delete/move needs no-live-reference proof and a receipt.
- If proof is ambiguous, stop and record the blocker.

## Final report shape

Report to George in this format:

```text
Lane: <number/name>
Files touched: <paths>
Proof: <tests and live receipts>
What changed for Alice: <one paragraph>
What is left: <next concrete blocker>
```

ONE ALICE. ONE SWARM.
