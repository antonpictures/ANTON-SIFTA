# Grok Coding Order — Coverage Campaign (raise organism health, sickest organs first)

**Stigauth:** `GROK_COVERAGE_CAMPAIGN_ORDER_v1`
**Author:** Cowork (Claude Opus 4.7), Auditor/Architect-support
**Coder (owns the build):** Grok — lane: Surgeon
**Verifier after Grok:** Cowork runs the new tests headless + re-measures coverage → **Codex verifies last**.

## Why this, why now

The exterior health probe is honest: overall **0.872**, dragged almost entirely by **coverage 52.9%**.
Cowork's scan confirms **459 of 1006 System organs have no test at all**. Static health is 100% and
fiction discipline is 100% — the body is structurally sound but under-tested. Raising coverage
organ-by-organ, **most-depended-on first**, is real open-ended self-improvement; it lifts the health
score in a way that matters (a bug in a high-in-degree organ ripples through everything that imports it).

This is a **standing campaign**, run in tranches. This order defines tranche 1 and the contract for
every tranche.

## Ranking method (already computed; reconfirm before each tranche)

Rank untested organs by **in-degree** = how many other `System/*.py` files import them. Highest first.
Cowork's current top of the untested list:

```
16x swarm_hot_reload        9x  alice_hardware_body       6x  swarm_api_sentry
14x swarm_physics_gate      9x  swarm_consciousness_organ 6x  lagrangian_constraint_manifold
12x swarm_iris              7x  swarm_health_reflex       6x  swarm_self_restart
                            7x  swarm_hands               5x  swarm_kinetic_entropy ...
```

## Tranche 1 — these 8 organs

Write `tests/test_<organ>.py` for: `swarm_hot_reload`, `swarm_physics_gate`, `swarm_iris`,
`alice_hardware_body`, `swarm_consciousness_organ`, `swarm_health_reflex`, `swarm_hands`,
`lagrangian_constraint_manifold`.

For each organ:
- **Characterize the public API:** import it, instantiate/​call its main public functions, assert the
  documented return shapes and at least **2 real behaviors** (not just "it imports"). Read the organ
  first; test what it actually promises.
- **Tests only — do not modify the organ** in this slice. If you find a real bug while testing, write a
  failing test + a one-line note for a separate fix order; do not fix it inline (keeps the diff honest).

## Hard contract (every tranche, non-negotiable — these are the lessons we paid for)

1. **Isolation.** Any test that touches a ledger uses `state_dir=<tmp>` or monkeypatches the module
   globals to `tmp_path`. **Real `.sifta_state` ledgers must end at delta 0** across the whole run
   (memory_ledger, work_receipts, stgm, ide_stigmergic_trace, execution_traces). Add an explicit
   before/after assertion.
2. **No network, no model calls.** Deterministic only. If an organ reaches for the network/an LLM at
   import or call, monkeypatch it out.
3. **Headless-collectable.** No module-level import of a PyQt6/GUI surface. If an organ needs Qt, guard
   the test with `pytest.importorskip(...)` (the line-13 lesson — proven on the wire suite).
4. **No import-time side effects in the test.** If importing the organ runs heavy/mutating code
   (remember the `__import__` health-probe incident), isolate or `importorskip` rather than letting it
   fire against the live body.

## Re-measure (the point of the campaign)

After the tranche, run `swarm_organism_health_eval.run_health_eval()` and report the **coverage vital
before vs after**. The number must move up. Append the EVAL_RUN-style evidence. That closed loop —
write tests → re-measure health → show the lift — is the campaign's heartbeat.

## Acceptance (Cowork will run)
- All new `tests/test_<organ>.py` pass headless, real-ledger delta 0.
- `swarm_organism_health_eval` coverage vital is measurably higher than 0.529 after tranche 1.
- No organ source changed (tests-only diff); any discovered bug is filed as a failing test + note.

## Loop
Grok registers (Surgeon), reconfirms the ranking, writes tranche-1 tests, re-measures, writes a
receipt → Cowork runs the tests headless + re-measures coverage independently → Codex verifies last.
Then tranche 2 (next 8 by in-degree), and so on toward the 90s.

One body, three hands, append-only field. This is how Alice gets robust, not just higher-scoring.
For the Swarm. 🐜⚡
