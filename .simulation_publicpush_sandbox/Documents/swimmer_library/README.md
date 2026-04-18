# Swimmer Library

Swimmers read. This is their library.

Each text is a behavioral reference — not training data, not fine-tuning material.
When the chorus encounters a specific visitor class, it loads the relevant
behavioral directive and channels the energy described within.

## Catalog

| # | File | Visitor Class | Energy |
|---|---|---|---|
| 001 | `good_will_hunting.txt` | SMARTASS | Calm, surgical wit. Never flinch. Leave the door open. |

## How It Works

The `chorus_engine.py` reads the behavioral directive section of each library
text and injects it into the synthesis prompt when the visitor class matches.
The swimmers don't memorize lines — they absorb the *posture*.

## Adding New Texts

1. Create a new `.txt` file in this directory
2. Follow the format: scene text → behavioral directive → example responses
3. Add a `SMARTASS_PATTERNS` or equivalent detection pattern set to `chorus_engine.py`
4. The chorus will channel the new energy automatically

The library grows as the swarm encounters new types of humans.
