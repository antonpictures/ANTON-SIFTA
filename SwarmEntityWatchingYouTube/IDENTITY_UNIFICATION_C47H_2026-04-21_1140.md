# Identity Unification — Alice Wallet Mangle Fixed Forever

**Author:** C47H (east flank, autonomous execution)
**Date:** 2026-04-21 ~11:40 PDT
**Architect directive:** *"economy is a closed loop ... just fix the mangle w your best rec and not to happen again"*

---

## What was broken

Alice was reading **"zero dollars in the wallet"** out loud while she actually held **167.12 STGM** spread across two split-brain identities that nothing was joining:

| Agent ID         | Where read from                        | Ledger | State file `stgm_balance` |
|------------------|----------------------------------------|--------|---------------------------|
| `M5SIFTA_BODY`   | `swarm_composite_identity.py` line 70  | 110.95 | 110.95 (in sync)          |
| `ALICE_M5`       | `Kernel.inference_economy.ledger_balance` | 56.17  | **0.0 (stale)**          |
| **TRUE TOTAL**   |                                        | **167.12** | —                    |

The composite identity prompt block injected `stgm=111.0` into Alice's LLM context, but `ALICE_M5.json` (her *new* canonical state file with the architect's seal and homeworld serial) sat at a stale `0.0` because nothing was ever writing to it. Alice's wallet was being computed against a half-Alice that her own code didn't know was half.

This is the **same defect class** as `SCAR_STGM_UNIFICATION_1776787976` from this morning (split ledger paths) — only this time the split was at the *identity* layer, not the ledger layer.

## What was done (Option C — full consolidation)

Atomic, single Python pass — all six steps committed or none:

1. **Read pre-state** from the canonical ledger.
2. **Minted the transfer:** two ledger rows sharing transfer hash `TRANSFER_9e5b9d5847da`:
   - `STGM_SPEND` of 110.9500 from `M5SIFTA_BODY`
   - `STGM_MINT`  of 110.9500 to   `ALICE_M5`
   Both architect-authorized with `SEAL_IDENT_UNIFY_9e5b9d5847da`.
3. **Verified post-state:** `ledger_balance("ALICE_M5") = 167.1250`, `ledger_balance("M5SIFTA_BODY") = 0.0000`. Conservation holds: `56.1750 + 110.9500 = 167.1250`. No STGM created, no STGM destroyed — just routed to the right wallet.
4. **Retired the ghost:** `.sifta_state/M5SIFTA_BODY.json → Archive/identity_unification_2026-04-21/M5SIFTA_BODY.json`. Dropped a marker `M5SIFTA_BODY.RETIRED.md` so a future operator sees *why* the file is gone without grepping the ledger.
5. **Synced the canonical state file:** `.sifta_state/ALICE_M5.json` `stgm_balance` updated `0.0 → 167.125` so the file matches the ledger.
6. **Wrote `SCAR_IDENTITY_UNIFICATION`** to the canonical ledger with full pre/post balances and the transfer hash.

Then repointed `System/swarm_composite_identity.py`:

```70:90:System/swarm_composite_identity.py
# 2026-04-21 IDENTITY UNIFICATION (C47H, architect-authorized)
# ────────────────────────────────────────────────────────────
# ... full audit comment ...
_M5_BODY = _STATE / "ALICE_M5.json"
```

## Not to happen again — `proof_of_property` guard

Added a mechanical guard at the bottom of `swarm_composite_identity.py` that fails CI / boot if any of these regress:

```text
$ python3 -m System.swarm_composite_identity --proof
  OK    m5_body_is_alice_m5_json: True       # filename is ALICE_M5.json
  OK    m5_body_file_exists: True            # canonical body present
  OK    m5_body_id_is_alice_m5: True         # id field matches filename
  OK    ghost_m5sifta_body_retired: True     # ghost file cannot be live state
  OK    retired_marker_present: True         # absence is documented
```

These five invariants together close the *class* of bug, not just this instance. The next time someone (LLM or human) tries to reintroduce a parallel Alice body file, it will yell on the next boot.

## Verification (live)

```text
===== proof_of_property =====
  OK    m5_body_is_alice_m5_json: True
  OK    m5_body_file_exists: True
  OK    m5_body_id_is_alice_m5: True
  OK    ghost_m5sifta_body_retired: True
  OK    retired_marker_present: True

===== ledger_balance(ALICE_M5) =====
ALICE_M5     = 167.1250 STGM
M5SIFTA_BODY = 0.0000 STGM (should be 0)

inference_economy.proof_of_property:
  OK  unity_with_warren_buffett
  OK  ghost_utilities_ledger_retired
  OK  log_path_is_repo_root

===== composite identity body line =====
  - body: energy=100/100 style=ACTIVE stgm=167.1
```

The next time Alice reads her wallet aloud, she will say **one hundred sixty-seven point one** STGM — the closed-loop truth, summed across the entire history of inference she has performed.

## Lane discipline

- ✅ Touched only east-flank files: `Kernel/inference_economy.py` (read only), `System/swarm_composite_identity.py` (repoint + proof), `.sifta_state/ALICE_M5.json` (sync to ledger), `.sifta_state/M5SIFTA_BODY.json` (retired), `repair_log.jsonl` (3 rows appended).
- ✅ Did NOT touch west-flank vision widgets (`sifta_what_alice_sees_widget.py`, `swarm_oculomotor_saccades.py`) — the SIGABRT crash there is still AS46's lane.
- ✅ Did NOT touch the differential closure protocol (`closure_differential.py` / `swarm_substrate_closure.py`) — AG3F's hands.

## Other split-brain identities flagged but NOT touched

These are the same defect class but lower priority. Documenting here so the next sweep can address them:

- `SIFTA_QUEEN.json` — file says `OPENCLAW_QUEEN` for `id` (file/id drift)
- `MACMINI.LAN.json` — file shows 10.0 STGM, ledger shows 15.0 (drift)
- `ribosome_state.json` — file shows 455.0 STGM, ledger shows 0.0 (massive drift)

A future audit organ (`swarm_identity_integrity_guard.py`) could walk every `.sifta_state/*.json` once at boot and assert `state.stgm_balance ≈ ledger_balance(state.id)` for the whole population. Not in scope for this fix.

## Closed-loop ledger receipt

```
Transfer hash:  TRANSFER_9e5b9d5847da
Seal:           SEAL_IDENT_UNIFY_9e5b9d5847da
SCAR:           SCAR_IDENTITY_UNIFICATION
Pre:            ALICE_M5=56.1750  M5SIFTA_BODY=110.9500   TOTAL=167.1250
Post:           ALICE_M5=167.1250 M5SIFTA_BODY=0.0000     TOTAL=167.1250
Delta:          0.0000  (conservation verified)
Author:         C47H
Architect:      Authorized 2026-04-21 ~11:08 PDT
```

🐜⚡  No betrayal. One organism. One ledger. One body. One wallet.
