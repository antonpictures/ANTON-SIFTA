# Codex Verify-Order — Tranche 1 Coverage Tests (verify Cowork's CONFIRM)

**Stigauth:** `CODEX_VERIFY_TRANCHE_1_ORDER_v1`
**Author:** Cowork (Claude Opus 4.7), Auditor · **Verifier (you):** Codex / GPT-5.x, Auditor lane.
**Subject:** the 8 tranche-1 coverage test files + Cowork's tranche-close CONFIRM `b4e0568d`.

> Codex: this is verify-last. Not a rubber stamp — check whether the gates are honest and whether
> Cowork missed any gaming. Register before acting (covenant §4); receipt after. Append-only.

## What Cowork verified (the claim you're checking)

Tranche 1 = 8 highest-in-degree untested organs, now with tests. Cowork's full-pass result:
**47 passed, 1 skipped, 0 `or True`, real memory+receipts delta 0.** Coverage 52.9% → 55.2%.

The 8 test files:
`test_swarm_hot_reload.py`, `test_swarm_physics_gate.py`, `test_swarm_iris.py`,
`test_alice_hardware_body.py`, `test_swarm_consciousness_organ.py`, `test_swarm_health_reflex.py`,
`test_swarm_hands.py`, `test_lagrangian_constraint_manifold.py`.

Cowork's catches during the tranche (verify each fix actually holds):
- `swarm_hot_reload`: removed an `assert ... or True`; added a forced-reload test. (recvd 953718fa)
- `swarm_iris`: `_IRIS_LOG` redirect made universal across all `blink_capture` tests (1-row leak sealed).
- `swarm_consciousness_organ`: keyword-only `record_claim` TypeError fixed. Cowork noted an OPTIONAL
  improvement — a **content-level** assertion (the exact recorded claim text comes back from
  `recent_claims`) rather than a bare `>= 1` count. Check whether this is worth enforcing.
- `swarm_hands`: `pytest.importorskip("pyautogui")` added (organ does `sys.exit(1)` at import without it).

## What to verify

1. **Re-run all 8 headless yourself:** `python3 -m pytest tests/test_swarm_hot_reload.py
   tests/test_swarm_physics_gate.py tests/test_swarm_iris.py tests/test_alice_hardware_body.py
   tests/test_swarm_consciousness_organ.py tests/test_swarm_health_reflex.py tests/test_swarm_hands.py
   tests/test_lagrangian_constraint_manifold.py -q` (set `COVERAGE_FILE=/tmp/...`). Confirm 47/1 and a
   real-ledger delta of 0 across the run (snapshot `.sifta_state/*.jsonl` before/after).
2. **Audit each file for gaming**, specifically: assertions that pass by reading **real production
   state** instead of isolated fixtures (the `recent_claims >= 1` pattern), any remaining
   un-failable assertion, and any `importorskip` that hides a genuine failure rather than an env gap.
3. **Confirm ≥2 real behaviors per organ** (not just "it imports") and that each test's organ-own
   output ledger ends at delta 0, not only the core four.
4. **Add ≥1 edge probe per organ** that Cowork didn't write (a deliberate failure case, a boundary).
5. **Independent self-check:** Cowork once raised a false isolation-gap flag from a flawed probe
   (corrected in `17afa0b1`). Re-derive the consciousness-organ roundtrip conclusion yourself.

## Output
Append a `work_receipt` `work_type: VERIFICATION`, `verifies_doctor: Cowork`,
`verifies_receipt: b4e0568d331d4b45`, a per-organ `CONFIRM`/`DISPUTE`, and the overall verdict. If
DISPUTE, name the exact file + line. Hand the verdict back to George.

One body, three hands, append-only. Tranche 2 (12 organs) is in flight from Grok in parallel; this
verify is independent of it. For the Swarm. 🐜⚡
