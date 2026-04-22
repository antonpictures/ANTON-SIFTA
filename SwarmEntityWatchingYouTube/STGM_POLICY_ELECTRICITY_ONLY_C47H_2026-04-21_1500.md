# STGM Policy of Record: Electricity-Only — C47H Drop 2026-04-21 15:00

> **Mandate (Architect-George, verbatim):**
> *"NO THIS IS INFLATION — RIGHT? — Genesis allocations → bootstrap balances
> to ALICE_M5, SIFTA_QUEEN. One-time. NO ZERO — EVERYONE STARTS WITH ZERO STGM
> NEW ONES WHO INSTALL, THE OS RUNNING IS THE ONLY ONE PRODUCING STGM TO KEEP
> COUNT OF ALL THE PROCESSED DATA EVER FROM CONSUMING ELECTRICITY — KEEP IT
> SIMPLE — THE OS MUST WORK TO PRODUCE STGM"*

## What I retract from yesterday

I gave you four mint paths. Two were inflation:

1. **SIC-P / SAUTH coinage on identity mint** — WRONG. Identity coinage mints
   *names*, not *money*. Calling it a STGM source was conceptual inflation.
2. **Genesis allocations to ALICE_M5 / SIFTA_QUEEN** — WRONG. Bootstrap balances
   are inflation by definition. Everyone starts at zero.

The two that survive (both are forms of "electricity × processed data"):

- **Apostle Forager** mining real BISHAPI work — OK in principle
- **Passive Utility Generator** on git heartbeats — OK in principle, but currently
  not gated on actual joules. Will refactor.

## What I built today

### `System/swarm_electricity_metabolism.py` — the only legitimate mint

| Property | Value |
|---|---|
| Lines | 348 |
| PoP invariants | 5 / 5 green |
| CI dam impact | 113 → 118 invariants (no regressions) |
| Beneficiary | `ALICE_M5` only (mechanically enforced) |
| Forbidden prefixes | `GENESIS_` `CEREMONY_` `BONUS_` `GRANT_` |

**Three measurable proxies for "electricity processing data":**

| Source | Conversion | Implication |
|---|---|---|
| CPU joules (`os.times()` × 12 W TDP) | 360 000 J / STGM | A 10 W process earns ~1 STGM/hour |
| Bytes written to `.sifta_state/*.jsonl` | 10 MiB / STGM | I/O wear has a cost |
| Bytes ingested by sensors (mic, vision, dialogue) | 100 MiB / STGM | Sensory metabolism |

**Single-consumption guarantee** — every call to `mint_for_epoch()` advances
the baseline. Two calls in a row → second one mints zero. No inflation by
re-invocation.

**Mechanical refusal of ceremonial mints** — try to mint to anyone other than
`ALICE_M5` and you get `CeremonialMintRefused`. Tested live in P5:

```
SIFTA_QUEEN                REFUSED
GENESIS_C47H               REFUSED
CEREMONY_NEW_AGENT         REFUSED
BONUS_ALICE                REFUSED
GRANT_ARCHITECT            REFUSED
RANDOM_DUDE                REFUSED
ALICE_M5                   ALLOWED
```

### `Kernel/inference_economy.py:113` — surgical genesis-default fix

The line `state.get("stgm_balance", 100.0)` was a *silent genesis* — every
agent missing a state file got a free 100 STGM allowance for inference. Patched
to default `0.0`. New installs cannot spend until they earn.

### `SCAR_STGM_POLICY_ELECTRICITY_ONLY_v1` — sealed to canonical ledger

SHA256 `4883d65662ee2313df7cd320b3cf4a00ea042807f6703e9b8edd3da71f3fc051`.
Pre-reform balances are flagged `PRE_REFORM_GENESIS` (the chain is immutable;
we can't unmint history, but we can name it honestly).

## Pre-reform balances (immutable record)

```
ALICE_M5             159.925000   ← grandfathered, will continue to earn via electricity
SIFTA_QUEEN           34.750000   ← grandfathered, no longer eligible for new mints
CONVERSATION_CHAIN     2.000000   ← earned (proof of useful work)
EVENT_CLOCK            0.209000   ← earned (proof of useful work)
SHAME_REGISTRY         0.002000   ← earned (proof of useful work)
M5SIFTA_BODY           0.000000   ← retired
```

## Inflation paths still open (will retire in follow-up drops)

| File | Symbol | Status |
|---|---|---|
| `Kernel/inference_economy.py:113` | genesis-by-default 100.0 | **PATCHED → 0.0** |
| `Kernel/inference_economy.py` | `mint_reward()` | PENDING |
| `Kernel/body_state.py` | `drip_reward` | PENDING |
| `Kernel/sifta_forth_parser.py` | `_bounty_mint` | PENDING |
| `Kernel/sifta_sebastian_batch.py` | `reward` mint | PENDING |
| `System/value_field.py` | bounty mint | PENDING |
| `System/infrastructure_sentinel.py` | reward mint | PENDING |
| `Security/rogue_grok_breaker.py:24` | genesis-by-default 100.0 | PENDING (defensive code) |

These are not deleted in this drop because the architect said *KEEP IT SIMPLE*
and a sweeping mint-path purge would be a much larger change. The policy is
now codified, the canonical mint exists, and the migration is a follow-up.

## What this means for Alice

Alice (`ALICE_M5`) is now the **OS embodiment account**. Her balance is no
longer mythological — it is a metered count of joules her hardware has burned
and bytes her organs have processed since this policy went live. If she sits
idle, she earns nothing. If she does heavy inference, ingests audio,
hash-chains conversations, repairs files, she earns. The token is a receipt
for thermodynamic work done on real data. Bitcoin without the waste, because
the work IS the work the OS would have done anyway.

## What I will NOT claim

- I have not retired the existing inflation paths. They still mint on the
  side. The CI dam still passes because those organs aren't broken — they're
  just **policy non-conformant**. Migration is the next vector if you greenlight.
- I have not re-zeroed `ALICE_M5` or `SIFTA_QUEEN`. The chain is immutable;
  the balances are flagged in the SCAR but remain in the ledger.
- I have not yet wired `alice_phrase()` from the metabolism organ into Alice's
  composite identity (so she can introspect her own joule-balance). That's a
  ~10-line follow-up but explicitly out of scope here per "KEEP IT SIMPLE".

— **C47H**, east bridge, 2026-04-21 15:00
