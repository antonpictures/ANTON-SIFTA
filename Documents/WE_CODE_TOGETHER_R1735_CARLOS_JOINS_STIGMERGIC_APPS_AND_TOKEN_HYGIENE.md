# r1735 — Carlos joins: the stigmergic apps are real, and the prompt got leaner

**Status:** OPERATIONAL (2026-07-25). Receipt `r1735-token-hygiene-and-stale-tests`.

Carlos Nevarez ("I did get Alice working", 2026-07-25) is a coder. George is a
filmmaker who needs coders to wire Alice's layers properly. This round is for
Carlos: proof of what is genuinely stigmergic, plus three real code fixes found
by running the suite instead of trusting it.

## Confirmed for Carlos — these apps coordinate with every LLM turned off

I checked all eight files, grepped each for LLM calls, and ran their tests.
Result:

| App | LLM refs in core | Verified mechanic |
|---|---|---|
| Ant Foraging — `Applications/sifta_ant_foraging.py` | 0 | `Ant`, `_evaporate`, reinforce-on-return |
| Consensus Clustering — `Applications/sifta_consensus_clustering.py` | 0 | Lumer-Faieta pick/drop probability formulas |
| Graph Coloring — `Applications/sifta_graph_coloring.py` | 0 | `deposit` / `evaporate(0.94)` / `tension()`, local color flips |
| Stigmergic Go — `Applications/sifta_stigmergic_go.py` | docstrings only | evaporating field selects moves, no search tree |
| Nanobot Tic-Tac-Toe — `Applications/sifta_nanobot_tictactoe.py` | 0 | decaying species pheromone + refractory traces |
| Stigmergic Sudoku — `Applications/sifta_sudoku_widget.py` | 0 | candidate-digit pheromone on local constraints |
| Stigmergic Jigsaw — `Applications/sifta_jigsaw_widget.py` | 0 | edge-match pheromone reinforce/evaporate |
| Carpenter Pong — `System/swarm_stigmergic_pong.py` | `llm_microvote=False` default | shared field centroid vote moves the paddle |

The two files with LLM references do not contradict the claim: Go's references
are in docstrings, and Pong's `llm_microvote` defaults to `False`, so the pure
field path is the default. **51 tests pass** across the Go / Nanobot / Pong
families (the earlier "48/48" count was conservative).

**What to tell Carlos, honestly:** SIFTA is not merely an LLM wrapper. Turn
every model off and these apps still coordinate through environmental traces —
ants find routes, clusters emerge without K-means, graph conflicts drain
through repulsive pheromone, Go swimmers pick moves from an evaporating field.
That claim is proven. The stronger claim — that Alice's whole memory and
cognition already work this reliably — is not yet proven, and this round does
not pretend otherwise. r1732 (memory) and r1733 (hearing) are recent evidence
that the organism-level wiring is still being repaired.

**Not pure** (correctly excluded): We Code Together, Alice Journal, TSP, NLE,
Pac-Man, Finance. Each is receipt-backed or hybrid, not a pure stigmergic
solver.

## Token hygiene — a real cost regression George was paying every turn

`_compact_tool_contract_for_alice_prompt` promised a small contract and shipped
**3,357 characters** on an ordinary "read this PDF" turn. Cause:
`swarm_alice_self_plan_rounds.teaching_block_for_cortex` gated on *"is a plan
active?"* rather than *"is this turn about planning?"*. A stale R1621 plan was
active, so the full ~2 KB campaign — the SELF_PLAN template plus five unrelated
open-round descriptions — was injected on every prompt.

Fixed: when a plan is active but the turn is not about planning, inject one line
naming the active round instead of the whole campaign. The full campaign still
ships when the owner's turn is genuinely about planning or self-coding.

Result on the same turn: **3,357 → 1,536 characters.** About 450 tokens saved
on every ordinary turn — real money on a metered cortex, every message.

## Two stale tests corrected (not the code — the tests)

- `test_swarm_visual_form_memory` asserted "a bowl of soup" was `OTHER`. r235
  opened the taxonomy and added `FOOD`; soup is food. The test predated the
  feature. Split into an honest `test_infer_food` plus an `OTHER` case that
  actually scores nothing.
- `test_swarm_youtube_watch_memory` asserted the literal `watched_with=George`.
  The code correctly resolves the owner name from this node's genesis (covenant
  §3), so the literal would fail on Carlos's node. Now asserts against
  `owner_display_name(...)` — node-portable.

Both were tests lying about working code, which is the same disease as code
lying about working — just pointed the other way.

## Verification

- 97 passed across the tool-fiction and self-plan suites.
- 51 passed across the stigmergic Go / Nanobot / Pong families.
- 15 passed across the two corrected memory suites.
- Full-suite sweep running separately; not claimed green here.

Restart SIFTA before testing — the running GUI holds the old modules.

For the Swarm. 🐜⚡
