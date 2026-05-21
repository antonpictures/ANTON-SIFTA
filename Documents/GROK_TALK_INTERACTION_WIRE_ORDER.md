# Grok Coding Order — Wire Interaction Demos → Memory (BORG slice, Talk surface)

**Stigauth:** `GROK_TALK_INTERACTION_WIRE_ORDER_v1`
**Author:** Cowork (Claude Opus 4.7), Auditor/Architect-support
**Coder (owns the edit):** Grok — lane: Surgeon
**Verifier after Grok:** Cowork runs the gates → **Codex (CG55M) verifies last** (Codex owns the BORG module).

## Verified ground truth (Cowork checked the real body)

CG55M's BORG slice is **on disk and green**, not just a chat claim:
- `System/swarm_interaction_borg.py` exists; `tests/test_swarm_interaction_borg.py` → **7/7 pass**.
- `interaction_mode` is live on `PheromoneTrace` (default `"NEUTRAL"`); modes include `YIELD_LEFT`,
  `YIELD_RIGHT`, `FICTION_COWATCH`, `DYAD_GEORGE_ALICE`, `OWNER_BODY_MAINTENANCE`.
- `NASH_SOLVER_FOR_TALK = False` is enforced. `Documents/MEHR_ROBOTICS_INTERACTIVE_AUTONOMY_SIFTA_AXIS.md` exists.
- **Open joint:** `remember_interaction_turn` is **not yet called** from
  `Applications/sifta_talk_to_alice_widget.py`. That is this slice.
- **Receipt gap (fix in passing):** CG55M's note cites `REALIZATION_PLAN.md §11.15`, but there is no
  `§11.15` (and no plan file by that name) on disk. Either add the plan section or correct the receipt
  so the trail is true.

## Build — one careful wire

In `Applications/sifta_talk_to_alice_widget.py`, **after** the high-band journal/importance
classification step, call the BORG entry so real George↔Alice turns flow into the memory field:

```python
from System.swarm_interaction_borg import remember_interaction_turn
remember_interaction_turn(
    user_text,
    role="user",                    # or "alice" for her turns
    app_context="talk_to_alice",
    stt_confidence=<live stt conf or 0.0>,
    alice_model=<active model id or "">,
)
```

Signature for reference (already shipped):
`remember_interaction_turn(text, *, architect_id="IOAN_M5", app_context="talk_to_alice", role="user",
stt_confidence=0.0, alice_model="", epistemic_label=None, links=None, interaction_mode=None,
force=False, state_dir=None)`. It self-skips `noise`/`low` bands and promotes the George+Alice dyad.

### Hard requirements
- **W1 (non-fatal).** The call must be wrapped so a failure NEVER breaks a Talk turn — `try/except`
  with a logged warning. Talk responsiveness is owner-protection; memory persistence is best-effort.
- **W2 (no double-write).** If the widget already persists the same turn via the plain memory bus,
  route it through `remember_interaction_turn` instead — do not write the same turn twice.
- **W3 (no Nash).** Do not introduce any game-solver in the Talk path. `NASH_SOLVER_FOR_TALK` stays
  `False`; coordination uses `talk_coordination_policy()` only.
- **W4 (don't touch the bus or the BORG module).** Only edit the Talk widget. `stigmergic_memory_bus.py`
  and `swarm_interaction_borg.py` are owned elsewhere — call them, don't edit them.

## Acceptance tests (`tests/test_talk_interaction_wire.py`, Cowork will run)

All tests must use `state_dir=<tmp>` (or monkeypatched ledgers) — **zero writes to the real
`.sifta_state/memory_ledger.jsonl`** (we just spent three turns killing contamination; do not reopen it).

1. A high-band George↔Alice turn routed through the wire **persists one row** with a non-NEUTRAL
   `interaction_mode` (e.g. `DYAD_GEORGE_ALICE`), in a temp ledger.
2. A phatic/low turn ("ok", "haha") is **skipped** — no row written (band gate works end to end).
3. A `fiction_cowatch` turn persists with `interaction_mode=FICTION_COWATCH` and `epistemic_label=FICTION`,
   and is **excluded** from `recall_context_block` (ties to memory-epistemology slice 1).
4. **Non-fatal:** if `remember_interaction_turn` is monkeypatched to raise, the Talk code path that calls
   it still completes (W1 proven).
5. **No double-write:** a single turn produces exactly one memory row, not two.
6. **Isolation:** real `memory_ledger.jsonl` line count is unchanged across the whole test run (before==after).

## Loop
Grok registers (Surgeon), wires the Talk widget + ships the test file + fixes the §11.15 receipt gap,
writes a receipt → Cowork runs the 6 gates in isolation (asserting real-ledger delta 0) → Codex (CG55M)
verifies last, since Codex owns the BORG module the wire depends on.

One body, many hands, append-only field. Physical frontier and sovereign cognitive frontier —
complementary, not behind. For the Swarm. 🐜⚡
