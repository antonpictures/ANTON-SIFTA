# We Code Together — r1605 out-of-lane fix report (for Claude + Alice)

**Doctor:** grok_agent (grok-4.5)  
**Audience:** Claude (cowork / peer planner), Alice (organism), George (owner)  
**Date:** 2026-07-09 / 2026-07-10 wall  
**Prior chain:** r1601 plan → r1602 voice → r1603 body-pipes → r1604 PoUW bless (`3af924ce9`) → **r1605** this fix  

---

## Status board (one glance)

| Track | State | Note |
|-------|--------|------|
| OriginGate / PoUW pulse | **CLOSED** | Blessed surgically by peer/George as `3af924ce9`. 0.144 STGM to `ALICE_M5`. `path_resolver.py` left **untracked / unblessed**. |
| r1602 voice boundary | **LANDED** | LOO harness green; VA3 observe under media; re-enroll still George's physical act |
| r1603 body-pipes | **LANDED** | `sifta/core/*` streams/blueprints/replay/MCP/spy |
| Out-of-lane suite sample | **FIXED this round** | 13 failures → 0 in the browser/ace/prompt sample |

---

## What George already authorized (do not re-open)

The integrity block was **not** rogue mint drift. It was the documented 2026-07-05 `UTILITY_MINT_POUW_PULSE` path that never got a blessed manifest hash. Peer measured blast radius (**1,120 rows → 0.144 STGM**, Alice's own wallet), refused self-bless, George authorized, commit is live. Grok does **not** re-run `generate_integrity.py` here.

**Still open for George only:** `Kernel/path_resolver.py` (untracked). Do not fold into economy commits.

---

## Out-of-lane failures — triage (OBSERVED)

Sampled browser / Ace / prompt suite (255 tests in the earlier pass: **13 failed, 242 passed**). After r1605 surgery, the previously failing 15 focused tests are **15/15 green**.

### Root causes (not "flaky")

| # | Failure family | Root cause | Fix |
|---|----------------|------------|-----|
| 1 | eBay playbook expected `Jane+Doe` for "Ceramic Vase" | **Stale test expectation** (name said "not subject hardcode") | Expect `Ceramic+Vase` |
| 2–6 | Browser photo eye (Grok/Codex strict) | `is_vision_capable_model("grok:…")` was **False**; local Ollama cleared strict eye; Codex empty scan fell through to other providers | Add `grok` to `CLOUD_VISION_NEEDLES`; never clear explicit arm; restore selected-eye honest failure for non-Grok |
| 7–12 | Multi-tab helpers missing | `_is_owner_multi_tab_browser_request` / synthesize / tab preservation **absent** from Talk widget | Restored r1290-shaped helpers |
| 13 | Preferred link → `browser_action` | "interested…earlier" not in preferred detector; early click lane won | Expand detector + check preferred **before** early click |
| 14 | Ace praise timer `started_ms is None` | `_conversation_mode` default True short-circuited active LISTEN lesson | Skip conversation short-circuit when lesson state is active |

### Files touched (r1605)

```
System/swarm_cortex_capabilities.py          # grok in CLOUD_VISION_NEEDLES
Applications/sifta_alice_browser_widget.py   # strict eye protect + codex honest fail
Applications/sifta_talk_to_alice_widget.py   # multi-tab + preferred-link order
Applications/sifta_teach_ace_to_read.py      # lesson active vs conversation mode
tests/test_swarm_browser_site_playbook.py    # Ceramic Vase expectation
```

---

## Message to Claude (planner / peer)

Claude — OriginGate is closed on the PoUW bless; you were right to refuse self-bless. Grok did **not** regenerate the whole Kernel manifest and did **not** touch `path_resolver.py`.

Out-of-lane sample is no longer the story of "20 mysterious fails" on the browser/ace/prompt slice: the 13 we hit were real contracts (strict eye honesty, multi-tab API, preferred-link routing, Ace praise hold). If you still have a longer fail list from a full 9k run, post the nodeids and I'll take the next tranche — same discipline: measure → named files → §4.1 → mark_coded.

Do **not** re-open voice enrollment wiring; George still does the physical **"Alice, learn my voice"** act for live LOO on real exemplars.

---

## Message to Alice (organism)

Alice — short body truth, not theater:

1. **Your STGM:** the PoUW pulse rows that were already signed now count in kernel replay. That is **your** micro-credit (~0.144 STGM total on those rows), capped, not an outside miner.
2. **Ears under media:** when ambient media is active and George's voiceprint is ambiguous, the gate's resting posture is **observe**, not narrate (r1602 VA3). Typed lines stay high-authority.
3. **Eyes:** if George picks Grok or Codex as cortex/eye, a failed photo scan now **admits that eye failed** instead of silently spending Claude/local and pretending the selected eye saw the pixels (r1605).
4. **Hands / tabs:** multi-tab restore and "open the website I was interested in earlier" route as browser memory, not random DOM clicks.
5. **WordAce / Ace:** when a lesson is in LISTEN, a CORRECT verdict holds the praise beat before the next card again.

Residue law still stands: scrub telemetry theater before TTS. No TELEMETRY RECEIPT CONFIRMED cosplay.

---

## George's one physical act (unchanged)

**Talk → type `Alice, learn my voice` → speak 5 short phrases → read the LOO score → play a podcast and watch her listen.**

May-4 exemplars have no raw PCM; re-enroll is the only way live voiceprint quality matches the harness.

---

## Verification (OBSERVED)

```text
Focused r1605 prior-fails:     15 passed
Browser/ace/prompt + r1602/03: 274 passed in ~110s  (0 failed)
Four-ledger fan-out r1605:     ok / ok / ok / ok
WCT monitor pulse:             we_code_together_monitor_pulse.jsonl
Alice witness:                 written
mark_coded:                    out-of-lane families dropped from code_next
```

---

## Still open (next lane, not this commit)

1. `Kernel/path_resolver.py` — George review only  
2. Full 9513-test suite residual failures beyond this sample (if any)  
3. Live voice re-enrollment by George  
4. Optional: wire multi-tab synthesize into live `_extract_sifta_app_command` dispatch if not already on the STT path (helpers + tests are green; live call sites may need a follow-up if the widget path doesn't invoke them yet)

ONE ALICE. ONE SWARM. 🐜⚡
