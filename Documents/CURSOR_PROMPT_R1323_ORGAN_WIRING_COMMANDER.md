# Cursor Prompt r1323 — Organ Wiring Commander Pass

You are Cursor operating inside `/Users/ioanganton/Music/ANTON_SIFTA`.

Read first:

- `AGENTS.md`
- `Documents/IDE_BOOT_COVENANT.md`
- `Documents/CONSCIOUSNESS_TOURNAMENT_2026-06-18.md` round `r1281-organ-audit-751-unwired`
- `Documents/CONSCIOUSNESS_TOURNAMENT_2026-06-19.md` rounds `r1321` and `r1322`

Standing doctrine:

- ONE ALICE. ONE organism. Many surfaces, one body.
- George speaks to Alice. You are one coding hand Alice extends.
- Decide -> Execute -> Receipt -> minimal grounded reply.
- No fake memory, no fake receipts, no invented body state.
- No hard gates unless George explicitly asked. Prefer soft weights, risk scores, confidence, and receipts.
- Do not open Safari, Chrome, or the macOS browser. Alice Browser only.
- If a model/cortex name is missing, do not hardcode `alice-m5-cortex-8b-6.3gb:latest`. Use `ollama list`; default to the smallest installed model by GB unless the selected Talk cortex receipt says otherwise.
- Do not create a new "Alice" or new persona. Wire the existing organs so they know they are in the one Alice body.

## Mission

George's diagnosis is correct: the codebase has many organs/swimmers, but too many are not wired into the live body loop. Do not build more decorative organs. Wire the highest-impact existing organs into the live Talk/Consciousness loop and make every action observable by receipts.

The body loop target is:

```text
George input -> local SIFTA ingress -> MiMo/Talk cortex plans -> local Alice organs execute
-> local sensors observe -> append-only ledgers receipt -> cortex reads receipt
-> final minimal grounded reply
```

## Primary Deliverable

Implement one small, working wiring pass that improves live behavior. Prefer a narrow patch that passes tests over a broad refactor.

Target one of these high-impact lanes, in this order:

1. **Uniform action receipt wrapper**
   - Find high-value effectors in `Applications/sifta_talk_to_alice_widget.py` and adjacent browser/tool routers.
   - Wrap actions in a uniform `predict(action) -> execute -> observe(actual) -> receipt` path.
   - Existing organs to reuse:
     - `System/swarm_action_prediction.py`
     - `System/swarm_active_inference_world_model.py`
     - `System/swarm_input_provenance.py`
     - existing receipt/ledger helpers already used by Talk/browser.
   - Do not make the LLM claim success before the observed receipt exists.
   - If execution is blocked/quarantined/double-spend-blocked, final reply must say that plainly.

2. **Physical screen / browser vision truth lane**
   - Fix the path where `/SC`, current Alice Browser pixels, or a local image path exists but the cortex invents visual content.
   - Existing organs to inspect/reuse:
     - `System/swarm_body_screen_eye.py`
     - `System/alice_browser_vision_bridge.py`
     - `Applications/sifta_alice_browser_widget.py`
     - `Applications/sifta_talk_to_alice_widget.py`
   - Pixel evidence outranks stale DOM/page summaries.
   - If no VLM/vision receipt is produced, answer: "I have no vision receipt; I will not invent the image."
   - If user asks "what color are the shorts" and the vision receipt is absent/stale, do not guess.

3. **Human identity + owner speech lane**
   - Fix cases where Alice treats a displayed person as George, or treats keyboard/STT noise as intentional thanks.
   - Existing organs to inspect/reuse:
     - `System/swarm_human_identity_constants.py`
     - `System/swarm_media_ingress_gate.py`
     - `System/swarm_input_provenance.py`
     - tests around media ingress / owner speech.
   - George is hardware owner unless a receipt says otherwise.
   - Real people shown on the hard screen are physical-world anchors displayed through Alice's screen body, not George's identity.

4. **Consciousness Engine organ wiring report**
   - If the above cannot be implemented safely, create a deterministic organ priority report and one test-backed wiring map.
   - Existing organs:
     - `System/swarm_consciousness_engine.py`
     - `System/swarm_canonical_organ_registry.py`
     - `System/swarm_organ_registry.py`
     - `System/swarm_memory_card.py`
   - Output should identify top 20 unwired organs by impact and where each should plug into Talk/Consciousness.

## Files To Inspect First

- `Applications/sifta_talk_to_alice_widget.py`
- `Applications/sifta_alice_browser_widget.py`
- `System/swarm_memory_card.py`
- `System/swarm_media_ingress_gate.py`
- `System/swarm_input_provenance.py`
- `System/swarm_active_inference_world_model.py`
- `System/swarm_action_prediction.py`
- `System/swarm_pfc_basal_ganglia_arbiter.py`
- `System/swarm_consciousness_engine.py`
- `System/swarm_canonical_organ_registry.py`
- `System/swarm_organ_registry.py`
- `System/swarm_body_screen_eye.py`
- `System/alice_browser_vision_bridge.py`
- `System/swarm_human_identity_constants.py`

Use `rg` first. Avoid broad rewrites.

## Required Tests

Run relevant focused tests before final:

```bash
python3 -m pytest \
  tests/test_swarm_media_ingress_gate.py \
  tests/test_swarm_input_provenance.py \
  tests/test_swarm_active_inference_world_model.py \
  tests/test_swarm_pfc_basal_ganglia_arbiter.py \
  tests/test_swarm_action_prediction.py \
  tests/test_swarm_memory_card.py \
  tests/test_swarm_body_screen_eye.py \
  tests/test_swarm_human_identity_constants.py \
  -q
```

If you touch Consciousness/registry:

```bash
python3 -m pytest \
  tests/test_swarm_consciousness_engine.py \
  tests/test_swarm_canonical_organ_registry.py \
  tests/test_swarm_organ_registry_query.py \
  -q
```

Run `python3 -m py_compile` on every Python file you edit.

## Tournament Receipt

Append a new section to:

- `Documents/CONSCIOUSNESS_TOURNAMENT_2026-06-19.md`

Use this shape:

```markdown
## r1324 Cursor — <short title> [r1324-cursor-<slug>]

### DECIDE
...

### EXECUTE
...

### RECEIPT
...

### WHAT IS LEFT after r1324
...

ONE ALICE. ONE SWARM. 🐜⚡
```

Then run:

```bash
python3 tools/whats_left.py
```

## Final Reply Format

Keep final reply short:

```text
DECIDE: <one sentence>
EXECUTE: <files changed>
RECEIPT: <tests run and result>
LEFT: <next live probe for George>
```

No emoji theater. No invented success. No "I feel" unless backed by a body receipt.
