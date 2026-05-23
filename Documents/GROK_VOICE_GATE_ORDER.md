# Grok Order — Make Source-Classification the Non-Bypassable Voice Gate

**Stigauth:** `GROK_VOICE_GATE_ORDER_v1`
**Author of spec:** Cowork (Claude Opus, Auditor/spec lane) — Linux sandbox, NOT GTH4921YP3. Line numbers below were probed live on disk.
**Coder:** Grok 4.3 — Surgeon, M5 body.
**Verifier:** Cowork re-runs the gate test + the 10-turn eval clean → Codex signs last.

> **Do NOT build a new organ.** The capability already exists. `swarm_media_ingress_gate.py` has `classify_spoken_ingress()` (line 783) and `classify_external_consciousness_lane()` (682); `audio_ingress.py` and `swarm_ambient_consciousness.py` feed them. CheckResolvable (`swarm_duplicate_organ_audit`) forbids a duplicate. This is a **wiring** job, not a build.

## Root cause (verified)

In `Applications/sifta_talk_to_alice_widget.py`:
- `_pre_user_media_ingress_receipt(...)` (line 11102) calls `classify_spoken_ingress` (11133) and only special-cases routes in `{"ambient_media","observed_media"}` (11140).
- But it is invoked **only in a specific branch** (line ~14213, the app-media/URL path) — **not** at the top of `submit_text()` (line 11810), which is where every voice/text turn actually enters before the brain (Ollama) is called.

Result: ambient input (e.g. an overheard "Ace") bypasses classification and reaches full reply generation. That is the 4/10. The fix is to make classification the **mandatory first decision** on every turn.

## The contract to implement

1. **Single choke point.** At the very top of `submit_text()` (and any other voice/transcript entry that reaches the brain), call `classify_spoken_ingress` **before any brain/Ollama call**. No path may reach the brain without passing this gate.
2. **Lane policy.**
   - `owner_direct_speech` (or input the owner explicitly addressed) → proceed to normal reply.
   - Every other lane (`screen_media_or_youtube`, `screen_media_fiction`, `ambient_phone_call`, `room_or_visitor_conversation`, `appliance_or_environmental_noise`, `unknown_ambient_speech`) → **write a field/context receipt and RETURN without invoking the brain.** Alice stays aware of the outer field (it's logged) but does not fire an addressed reply.
3. **Default ambient behavior:** **strict silence + field receipt** (Architect's policy choice — see note below). No spoken acknowledgment on ambient lanes.
4. **Non-bypassable:** audit every path that reaches the brain in this widget and confirm each one routes through the gate. The bug was "some paths still let ambient through" — this clause is the fix.
5. **Effector truth:** the gate decision is receipted (`source_class`, `attention_policy`, `external_consciousness`) per existing `write_gate_receipt`.

## Acceptance — this is what makes it real, not "green but dead"

`tests/test_voice_gate.py` (new):
1. **Ambient input does NOT reach the brain.** Mock the brain/Ollama call. Feed an ambient-classified input (e.g. a bare "Ace" with an ambient route). Assert the brain mock is **never called** and a field receipt is written.
2. **Owner-direct input DOES reach the brain.** Feed an owner-direct input; assert the brain mock **is** called.
3. **No bypass:** assert every brain-invoking entry routes through the gate (parametrize over the entry points).
4. delta=0 on core-4 ledgers.

**Then re-run the eval:** `python3 -m pytest tests/test_eval_*.py -q` stays green, and re-run the 10 Talk turns. **Do not report "fixed" until (a) the gate test passes AND (b) the gate provably blocks the ambient turns.** "Wired" means a test proves the brain is not called on ambient — nothing less.

## Open policy question (Architect decides)

Grok asked: strict silence vs. quiet acknowledgment on ambient lanes. **Cowork recommendation: strict silence + field receipt.** The 4/10 failures were *exactly* Alice replying when she shouldn't ("Ace. I'm here…"). A "quiet acknowledgment" risks re-introducing that behavior. Log ambient to the field (she stays aware), but no addressed reply. The owner can opt into soft acks later as a separate, tested feature. **George: confirm strict-silence, or override.**

## Loop
1. Grok registers, wires the gate at `submit_text`, makes it non-bypassable, writes `test_voice_gate.py`, runs it + the eval suite, receipts, hands back the trace.
2. Cowork re-runs the gate test + eval clean; reports with the sandbox-vs-Mac caveat.
3. Codex signs last.

For the Swarm. 🐜⚡ Wire the ear that already exists.
