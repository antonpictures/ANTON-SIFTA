# Economy — Genesis Mint Audit (Architect reference)

## Sealed: Agent install (`Applications/sifta_finance.py`)

- `InstallAgentDialog` has **no** “Starting STGM” field.
- `_install()` hardcodes `stgm = 0.0`.
- Genesis log records `starting_stgm: 0.0` with Ed25519 `architect_seal`.
- **No** `STGM_MINT` row is written at install time.

Swimmers are born at **0** and earn through ledger-quorum work (`repair_log.jsonl`).

## Separate policy: Passive utility (`passive_utility_generator.py`)

This is **not** birth mint. If the thermal loop is running, it periodically writes signed `UTILITY_MINT` rows for agents that have state files.

- To disable automatic passive mints: `export SIFTA_PASSIVE_UTILITY_MINT=0`
- When disabled, the utility burn loop does not mint (idle).

## Ledger truth

Canonical balances: `inference_economy.ledger_balance(agent_id)` reading **both** ledger dialects in `repair_log.jsonl`.

## Warren Buffett (`System/warren_buffett.py`)

- **OBSERVE-only** — no mint, no spend.
- Passively scans `repair_log.jsonl` and summarizes mining / foundation / utility / spend.
- Reports **architect-local** STGM as the sum of `ledger_balance()` for agents whose `.sifta_state/*.json` lists the **local** `homeworld_serial` (this machine’s swimmers).

## FOUNDATION_GRANT

Supported as a dialect in `inference_economy` for legacy rows. Warren’s report counts `foundation_grant_rows`. Policy: do not issue new foundation grants except explicit human-governed ceremonies.

---

*The loop closes in code, not in chat.*
