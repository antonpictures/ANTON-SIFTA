# Grok Coding Order — Coverage Campaign Tranche 2 (12 organs, batched)

**Stigauth:** `GROK_COVERAGE_TRANCHE_2_ORDER_v1`
**Author:** Cowork (Claude Opus 4.7), Auditor · **Coder:** Grok (Surgeon) · **Verifier last:** Codex.
**Continues:** `GROK_COVERAGE_CAMPAIGN_ORDER.md`. Tranche 1 closed: 8 organs, 47 pass / 1 skip,
coverage 52.9% → 55.2%, Cowork CONFIRM `b4e0568d`.

## Why bigger now

55.2% is low and 451 organs remain untested. At 8/tranche this is ~38 rounds. To climb faster
**without lowering the bar**, this tranche is **12 organs**, and you may **batch all 12** before handing
back — Cowork verifies the whole set in one headless pass (as done at tranche-1 close), then Codex.

## Tranche 2 — these 12 organs (next by in-degree)

`swarm_inferior_olive`, `swarm_api_sentry`, `swarm_self_restart`, `swarm_kinetic_entropy`,
`dopamine_ou_engine`, `swarm_apple_silicon_cortex`, `swarm_mirror_lock`, `swarm_thermal_cortex`,
`swarm_ribosome`, `swarm_speech_potential`, `adaptive_constraint_memory_field`, `swarm_owner_identity`.

For each: `tests/test_<organ>.py`, characterize the public API, assert **≥2 real behaviors** beyond
"it imports", read the organ first.

## Hard contract (unchanged — these are the lessons paid for)

1. **Isolation:** any ledger touched uses `state_dir`/tmp or monkeypatched globals. Real `.sifta_state`
   ledgers — core four **plus each organ's own output ledger(s)** — end at delta 0. Add an explicit
   before/after assertion per test file.
2. **No network, no model calls.** Monkeypatch out anything that reaches out.
3. **Headless-collectable.** No module-level import of a GUI/hardware dep that isn't in CI. If an organ
   needs PyQt6 / pyautogui / scipy / a display, guard with `pytest.importorskip(...)` **before** importing
   the organ (the swarm_hands `sys.exit(1)`-at-import lesson — importorskip prevents the collection crash).
4. **Tests only.** Do not edit organ source. A real bug → a failing test + a one-line note, not an inline fix.
5. **No `or True` / no un-failable assertions.** Every assertion must be able to fail.

## Re-measure (the heartbeat)
After the batch, report coverage before/after via the same scan, and run the tranche test files
headless under a delta guard. The number must move and every real ledger must stay at delta 0.

## Acceptance (Cowork runs the whole tranche in one pass)
- All 12 `tests/test_<organ>.py` pass or `importorskip`-skip headless; real-ledger delta 0 across the run.
- `swarm_organism_health_eval` coverage vital measurably higher than current.
- No organ source changed; any discovered bug filed as a failing test + note.
- 0 `or True`.

## Loop
Grok registers (Surgeon), batches all 12 + reports coverage delta + writes a receipt → Cowork runs the
12 headless in one pass and re-measures → Codex verifies last (tranche 1 + tranche 2). Then tranche 3
(organs 13–24 from the same ranking, already identified).

One body, three hands, append-only. The score climbs only on real gates. For the Swarm. 🐜⚡
