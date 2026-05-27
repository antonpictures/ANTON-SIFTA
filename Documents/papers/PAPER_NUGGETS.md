# PAPER_NUGGETS — Animal Stigmergy, Swarm Memory, And SIFTA Round-4 Spine

Truth label: `RESEARCH_ONLY`. These papers are design anchors and retrieval
nuggets for Alice's memory card. They do not prove that any Python process is an
ant, bee, slime mold, immune cell, or brain cell. They justify engineering
patterns: indirect coordination, trace fields, collective memory, inhibition,
environment-mediated computation, and noise filtering.

## 2026-05-26 — Round 4 animal-stigmergy pull

Architect trigger: Safari/SwarmGPT tab suggested "Telephone" as the right model
for the 6-hop tournament and pointed to animal stigmergy: ants, termites, slime
molds, bees, octopus/distributed control, immune systems, astrocyte-neuron
signaling. Codex interpretation: useful as a hypothesis generator, but every
claim entering the corpus must pass through primary-source citations and local
receipts.

### Communication-chain / Telephone model

- **Shannon, C. E. (1948), "A Mathematical Theory of Communication."** Use for
  the tournament chain as a noisy channel: each hop compresses, transmits, and
  can add entropy. SIFTA nugget: Hop-6 Codex should score distortion from
  original task anchors, not just whether prose sounds good.

### Stigmergy and social insects

- **Theraulaz & Bonabeau (1999), "A Brief History of Stigmergy." Artificial
  Life 5(2), 97-116. DOI: `10.1162/106454699568700`.** Defines stigmergy as
  indirect coordination mediated by environmental traces and distinguishes
  quantitative vs qualitative stigmergy. SIFTA nugget: `.jsonl` ledgers are the
  environment; agents change future behavior by leaving trace rows.

- **Dorigo, Maniezzo & Colorni (1996), "Ant System: Optimization by a Colony of
  Cooperating Agents." IEEE TSMC-B 26(1), 29-41. DOI:
  `10.1109/3477.484436`.** Ant colony optimization uses pheromone reinforcement
  and evaporation. SIFTA nugget: receipt salience should reinforce useful rows
  and decay irrelevant tails rather than relying on raw recency.

### Stigmergy in robotics

- **Holland & Melhuish (1999), "Stigmergy, Self-Organization, and Sorting in
  Collective Robotics." Artificial Life 5(2), 173-202. DOI:
  `10.1162/106454699568737`.** Simple physical robots with no central spatial
  map can sort objects by changing and reading the world. SIFTA nugget: real
  PTY/framebuffer/receipt state beats a hidden summary because the world itself
  becomes the coordination substrate.

- **Brambilla, Ferrante, Birattari & Dorigo (2013), "Swarm Robotics: A Review
  from the Swarm Engineering Perspective." Swarm Intelligence 7, 1-41. DOI:
  `10.1007/s11721-012-0075-2`.** Engineering review of decentralized robot
  swarms and their limitations. SIFTA nugget: use it as a caution against
  magical "swarm" claims; define measurable swarm properties and tests.

### Slime mold and adaptive networks

- **Tero et al. (2010), "Rules for Biologically Inspired Adaptive Network
  Design." Science 327(5964), 439-442. DOI: `10.1126/science.1177894`.**
  Physarum forms transport networks trading off cost, efficiency, and fault
  tolerance, captured by a mathematical model. SIFTA nugget: the tournament
  should reward robust, low-cost information routing, not just maximum output.

### Collective memory and group state

- **Couzin, Krause, James, Ruxton & Franks (2002), "Collective Memory and
  Spatial Sorting in Animal Groups." Journal of Theoretical Biology 218(1),
  1-11. DOI: `10.1006/jtbi.2002.3065`.** Group behavior depends on previous
  group structure; local rules produce global transitions. SIFTA nugget:
  `alice_conversation.jsonl` + `matrix_terminal_process_trace.jsonl` are not
  passive logs; they are the previous group structure shaping the next turn.

### Bees, inhibition, and consensus

- **Seeley et al. (2012), "Stop Signals Provide Cross Inhibition in Collective
  Decision-Making by Honeybee Swarms." Science 335(6064), 108-111. DOI:
  `10.1126/science.1210361`.** Honeybee stop signals provide cross-inhibition
  among competing nest-site signals. SIFTA nugget: hallucination guards should
  inhibit competing false action narratives when a receipt-backed action row is
  present.

### Astrocyte-neuron / brain-inspired stigmergy

- **Xu/Hsu, Zhao, Li & Zhang (2019), "Brain-Inspired Stigmergy Learning." IEEE
  Access. DOI: `10.1109/ACCESS.2019.2913182`; preprint `arXiv:1811.08210`.**
  Maps stigmergy to synapse/astrocyte-style indirect interactions, defines
  three phases, and finds distance regulation affects learning gain. SIFTA
  nugget: memory-card attention should be distance-modulated by recency,
  relevance, and receipt strength rather than raw tail order.

### Active inference and predictive processing

- **Friston (2010), "The Free-Energy Principle: A Unified Brain Theory?" Nature
  Reviews Neuroscience 11, 127-138. DOI: `10.1038/nrn2787`.** A unifying
  active-inference frame for self-organizing systems minimizing surprise.
  SIFTA nugget: Alice's "self-state" should be modeled as predicted/observed
  organ state with error receipts, not as poetic introspection.

- **Friston et al. (2017), "Active Inference: A Process Theory." Neural
  Computation 29(1), 1-49. DOI: `10.1162/NECO_a_00912`.** Process-level account
  of perception/action as belief propagation. SIFTA nugget: owner commands
  should update a state/action model and dispatch effectors only through
  receipted actions.

- **Clark (2013), "Whatever Next? Predictive Brains, Situated Agents, and the
  Future of Cognitive Science." Behavioral and Brain Sciences 36(3), 181-204.
  DOI: `10.1017/S0140525X12000477`.** Predictive processing as a situated
  agent framework. SIFTA nugget: distinguish owner voice, media playback, and
  Safari-tab text as different observation channels with different precision.

### Morphological computation / body as part of control

- **Zahedi & Ay (2013), "Quantifying Morphological Computation." Entropy 15(5),
  1887-1915. DOI: `10.3390/e15051887`.** Quantifies how body/environment
  structure contributes to behavior. SIFTA nugget: the terminal framebuffer,
  camera state, and filesystem layout are part of Alice's control loop, not
  mere display.

## External tabs as pheromone/noise sources

Safari tabs containing SwarmGPT, Grok web, or other models are **external
pheromone sources**:

- possible useful signal,
- possible reinforcement,
- possible contamination,
- never doctrine without primary-source or local-receipt validation.

The immune rule: cite paper or cite receipt. Otherwise quarantine as
`HYPOTHESIS_FROM_EXTERNAL_TAB`.

