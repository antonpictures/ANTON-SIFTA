# System Patterns

## Core Architecture
- One Alice, many surfaces/hands
- All surfaces share `.sifta_state/` ledgers and global conversation
- Predator Gate (registration + append-only traces) for every IDE doctor mutation
- Real hardware-bound swimmers/organs produce STGM receipts
- IDE doctors in sandbox produce only MANA coordination traces

## Key Patterns
- Stigmergy: coordination through shared environment (ledgers, field vectors) rather than direct messaging
- Receipt-first: almost every action that matters writes an append-only row before or immediately after
- Narrow surfaces: prefer small, receipted, verifiable changes over large refactors
- Multi-doctor collision discipline with explicit round numbering and correction rows

## Important Boundaries
- Sandbox doctors ≠ hardware swimmers
- MANA ≠ STGM (no conversion, no claim)
- IDE traces are useful for coordination but must never be treated as cryptographic hardware proof unless they carry real signatures
