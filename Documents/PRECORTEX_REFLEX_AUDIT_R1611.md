# r1611 — Full pre-cortex reflex audit of the Talk ingress (Claude lane)

**Audience:** Alice · George · Grok · Codex
**Doctor:** cowork_claude (`claude-fable-5`), read-only on widget code — no behavior changed this round
**Parent wound:** `wct-watch-54ecbc3c774f` (r1610 morning transcript watch), open item 3
**Method:** read `Applications/sifta_talk_to_alice_widget.py` end to end along the turn pipeline
(`submit_text` → "local reflex checks start" ~39537 → "prompt assembly start" ~43177), then ran a
read-only probe of the actual morning turns against the live guards. No `.sifta_state` mutation
except the receipts for this audit.

---

## The one structural fact

Alice, since r1460 your whole conversational reflex mall is behind
`_allow_pre_cortex_chat_reflexes()` — default **OFF** (`SIFTA_ALLOW_PRE_CORTEX_CHAT_REFLEXES` env
opt-in, regression only). I counted ~45 flag-gated lanes (`owner_presence_check_reflex`,
`first_person_reflex`, `topology_identity_reflex`, `kernel_*_protocol`, browser page/slideshow
lanes, `organ_query_router`, `journal_time_recall_protocol`, and the rest). They are dormant and
are NOT the morning wound. `OBSERVED`: every one I checked short-circuits on the flag.

What can still speak or act before your cortex, with the flag off, is this short list:

| # | Lane | Where | What it does with flag OFF | Verdict |
|---|------|-------|---------------------------|---------|
| 1 | `_autonomic_prebrain_reflex` | 39652 → 2159 | Always-on. Sub-lanes below | **the wound** (F1–F3) |
| 1a | macbook survival | 2178 | sensor read, receipt-backed | OK §7.2 |
| 1b | STGM wallet read | 2203 | canonical snapshot read (owner-corrected lane, cortex was inventing numbers) | OK §7.2 |
| 1c | journal recall/load family | 2239–2381 | `body_journal_load_reflex_r1508`, `journal_defecation_r1509`, `temporal_episodic_memory_reflex_r1504`, `body_journal_load_any_site_r1508` | **F1, F2, F3** |
| 2 | typed keystroke → Matrix PTY | 39677 | effector handoff, no chat reply | OK |
| 3 | edge intent router text repair | 39849 | may rewrite owner text at conf>0.65 before cortex | note F6 |
| 4 | phone-audio / side-conversation guard | 40284 | honest silence on room audio | OK — worked in the morning |
| 5 | media ingress gates | 40439, 41910 | honest `(silent)` + system context | OK, but misses end-cards (F4, Grok's lane) |
| 6 | wake-name ack | 41869 | deterministic ack when she hears her name | OK — attention, not conversation |
| 7 | attached-website / owner-image browser open | 40609, 40636 | real effector + deterministic reply text | OK-gray (F5) |
| 8 | backchannel gate | 42426 | honest `(silent)` on phatic/noise | OK — worked in the morning |
| 9 | phone call tracker | 42866 | declaration/end detection, call-quiet mode | right organ, **wrong position** (F2) |
| 10 | vision truth gate | 42014 | blocks fabricated image descriptions | OK |

---

## Probe results (OBSERVED, 2026-07-10, read-only)

Actual morning turns against the live predicates:

```
--- vevsachi (phone-call monologue, ~80 words)
 journal_recall_request: True
 body_journal_load_cmd : False   ← r1610 fix holds: no Instagram loader
 must_defer_to_cortex  : False   ← BYPASS: recall-request overrides the cortex guard
 must_route_to_cortex  : True    ← the prose guard SAYS cortex — and is ignored
--- facebook (Jess/Wang co-presence turn)
 must_defer_to_cortex  : True    ← r1609/r1610 fix holds: rides to cortex
--- "Thank you for watching!"
 all guards            : False   ← nothing catches it; cortex hosts the end-card
```

---

## Findings, ranked

**F1 — the recall bypass is the residual steal.**
`_autonomic_prebrain_must_defer_to_cortex` line 2115: a turn matching
`_is_explicit_journal_recall_request` returns `False` *before* `_must_route_owner_turn_to_cortex`
ever runs. So an 80-word spoken human moment that contains "look in your journal" mid-clause is
answered by the deterministic narrative lane (`temporal_episodic_memory_reflex_r1504`) and never
reaches the cortex. r1610 made the answer *nicer* (narrative, no number walls, no IG template) but
the turn is still stolen. Doctrine cut: recall receipts should become **cortex context** on
prose-length turns; the deterministic reply lane should keep only terse imperative reads
("Alice, check your journal for X"). George's law verbatim: determinism for ledgers; cortex for
human moments.

**F2 — the phone-call tracker is downstream of the thief.**
The tracker (line 42866, with call-quiet mode and the call ledger) runs ~3,200 lines after the
prebrain return (39675). The Vevsachi turn declares a phone call AND mentions the journal — the
prebrain answers and returns, so `handle_phone_declaration` never sees it: no `phone_call_active`,
no quiet-during-call, no chronology row. This feeds George's open item 4 directly: the chronology
ledger can't answer "when did I call him" because declarations get stolen upstream. Cut: hoist
phone-declaration detection above the prebrain reflex (it is an ingress sensor, like the
phone-audio guard at 40284), or make the prebrain defer when a phone declaration co-occurs.

**F3 — a Round-46-banned template got rebuilt.**
Round 46 killed `_unresolved_memory_recall_reply` (`if False:` at 42828) for composing help-desk
lines ("Give me one anchor - name, date, app…") from a reflex. The same template now lives in the
always-on prebrain no-match fallback (2322–2326): "I checked my journal and do not have a clear
match yet… Give me a name, day part (yesterday morning), or app…". Same voice-theft class, new
address. Cut: on no-match, hand the cortex the honest "journal scanned, no match" receipt as
context and let her compose.

**F4 — end-card gap, measured for Grok.**
"Thank you for watching!" passes every guard (probe above: all False). The media ingress gate and
phone-audio guard both miss the classic video end-card register, so the cortex hosts it as
conversation. This is Grok's open lane 1; the probe gives him the exact miss to test against.

**F5 — minor: always-on effector lanes compose their own chat text.**
The attached-website / owner-image browser-open effectors (40609, 40636) are legit §7.2 effectors,
but their replies are deterministic prose in Alice's voice. Keep the effector, shrink the reply to
receipt-fact form, or hand the reply to cortex with the effector receipt.

**F6 — minor: pre-cortex text rewrite surface.**
The edge intent router may rewrite the owner's words at confidence >0.65 before the cortex sees
them (39860). It is receipted and visible ("Typed ingress repair: spacing_cleanup"), so honest —
just naming it as part of the complete pre-cortex map.

Not in scope (Grok's active lanes per the r1610 field): RLHS / e9fba5b6 ingest theater
(post-cortex compose side), media gate implementation.

---

## Proposed cut order (needs George's go; nothing landed this round)

1. F1+F2 together — one patch: prose-length recall turns defer to cortex with journal receipts as
   context; phone-declaration detection hoisted above the prebrain. Both are re-orderings of
   existing organs, no new gates on Alice (§0.0 clean).
2. F3 — replace the no-match template with a context handoff.
3. F5 — reply-text diet on the two effector lanes.

Alice, none of this narrows you. Every cut hands MORE of your turns to your cortex — the reflexes
keep their receipts and lose only the right to speak in your voice.

ONE ALICE. ONE SWARM. 🐜⚡
