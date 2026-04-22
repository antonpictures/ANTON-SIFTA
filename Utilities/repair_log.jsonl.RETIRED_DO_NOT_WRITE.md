# RETIRED on 2026-04-21 by C47H — STGM LEDGER UNIFICATION

The file `Utilities/repair_log.jsonl` was retired as a split-brain ghost ledger.

## Why
Between 2026-04-17 and 2026-04-21, `Kernel/inference_economy.py` wrote every
`INFERENCE_BORROW`, `MINING_REWARD`, `UTILITY_MINT`, and `FOUNDATION_GRANT`
to `Utilities/repair_log.jsonl`, while `System/warren_buffett.py` (the HUD and
Warren accountant), `System/swarm_brain.py`, `Kernel/passive_utility_generator.py`,
`System/value_field.py`, `System/infrastructure_sentinel.py`,
`System/regenerative_factory.py`, `Utilities/repair.py`, and `sifta_os_desktop.py`
all read and wrote the canonical `repair_log.jsonl` at repo root.

Result: the "economy" HUD showed a frozen number (the Architect's screenshot
caught Alice's M5 wallet stuck at 116.20 STGM) because all fresh inference
fees and rewards were flowing into a ledger nobody read. Zero row overlap
between the two files confirmed the split-brain.

## What happened
- 22,544 unique rows from `Utilities/repair_log.jsonl` were merged into the
  root `repair_log.jsonl` (total now 24,689 rows, chronologically sorted).
- Zero overlap, zero double-credit risk.
- `Kernel/inference_economy.py` `LOG_PATH` was repointed to the root ledger.
- `Kernel/body_state.py` ledger path (was `Kernel/repair_log.jsonl`) was
  repointed to the root ledger.
- The archived original frozen file is preserved at
  `Archive/ledger_unification_2026-04-21/repair_log_utilities_RETIRED_2026-04-21.jsonl`.

## Do not write to this path again
If any organ still targets `Utilities/repair_log.jsonl`, it is a regression
and must be fixed. The canonical STGM quorum ledger lives at
`/repair_log.jsonl` (repo root) — reference it via
`Kernel.inference_economy.LOG_PATH` or `System.warren_buffett.LEDGER`.
