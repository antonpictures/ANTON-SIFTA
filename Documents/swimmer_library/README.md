# Swimmer Library

Swimmers read. This is their library.

## Couch / Lounge / Library — the same room

Architect doctrine (canonical): **the couch**, **the lounge**, and **the library** name the **same stigmergic space** — rest, cross-pollination, and curated reading — expressed on three substrate layers:

| Layer | What it is | Where it lives |
|------|------------|----------------|
| **The Couch** | Visual center of the Swarm Lounge — swimmers drift here to idle and blend | `Applications/sifta_lounge_widget.py` — dark oval, “THE LOUNGE” |
| **The Lounge** | Cross-domain gossip + physics-parameter transfer when the OS idles | `.sifta_state/lounge_gossip_ledger.jsonl` — see `Documents/APP_HELP.md` § Swarm Lounge |
| **This folder** (`Documents/swimmer_library/`) | **Narrative / movie-script** and behavioral posture texts swimmers channel through the chorus (e.g. `good_will_hunting.txt`) | Read by `chorus_engine.py` when visitor class matches — *posture*, not memorized lines |
| **Stigmergic Library (ledger)** | Ultra-dense **factual** nuggets mined via BISHAPI, Spleen + Microglia filtered | `.sifta_state/stigmergic_library.jsonl` — CLI: `Applications/sifta_library.py` |

Nothing here contradicts the others: **fiction and posture** live in **this directory**; **gossip physics** in the lounge ledger; **empirical nuggets** in `stigmergic_library.jsonl`. Alice does not confuse them — she routes by purpose. Movie scripts on the couch **remain valid**: they are exactly these files, plus the lounge as the *place* swimmers gather, plus the new ledger as *another shelf* in the same room.

---

Each text below is a behavioral reference — not training data, not fine-tuning material.
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
