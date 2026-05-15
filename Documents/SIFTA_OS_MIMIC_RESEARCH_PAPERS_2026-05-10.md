# SIFTA OS Mimic Research Papers — 2026-05-10

**Purpose:** turn the YouTube swarm/OS intuition into a receipt-backed research spine for SIFTA Predator v7. This is not decoration. Each paper maps to an implementation habit: register, sense, decide, execute, receipt, update the field, and give George a minimal grounded reply.

**Boundary:** SIFTA keeps the macOS/PyQt body. These papers inform the Python organism inside `sifta_os_desktop.py`; they do not justify Linux daemons, detached Alice services, surveillance, military use, or unreceipted autonomy.

## 1. Environment As Memory

- Grassé, P.-P. (1959). *La reconstruction du nid et les coordinations interindividuelles chez Bellicositermes natalensis et Cubitermes sp.; la théorie de la stigmergie.* `Insectes Sociaux`, 6, 41-80. DOI: <https://doi.org/10.1007/BF02223791>
  - SIFTA mimic: `.sifta_state/*.jsonl` is the nest wall. Organs do not coordinate by vibes; they leave structured traces that trigger later work.
  - Code vector: every process table heartbeat writes a receipt; every organ reads recent field state before acting.

- Bonabeau, E., Dorigo, M., & Theraulaz, G. (1999). *Swarm Intelligence: From Natural to Artificial Systems.* Oxford University Press. DOI: <https://doi.org/10.1093/oso/9780195131581.001.0001>
  - SIFTA mimic: simple local organ rules can produce coherent organism behavior when mediated by a shared field.
  - Code vector: keep organ APIs small: `register`, `heartbeat`, `budget_state_for`, `list_unhealthy`, field read/write.

## 2. Swarm Search And Profitability

- Kennedy, J., & Eberhart, R. (1995). *Particle Swarm Optimization.* Proceedings of ICNN'95, 1942-1948. DOI: <https://doi.org/10.1109/ICNN.1995.488968>
  - SIFTA mimic: each agent arm keeps personal best evidence; the organism keeps global best routes. Balance inertia, individual memory, and social pull.
  - Code vector: Corvid/Hermes/Codex task outcomes update a shared scoreboard: `task_type`, `stgm_delta`, `receipt_id`, `quality`, `latency`.

- Eberhart, R., & Kennedy, J. (1995). *A New Optimizer Using Particle Swarm Theory.* MHS'95. DOI: <https://doi.org/10.1109/MHS.1995.494215>
  - SIFTA mimic: cheap exploratory swimmers are useful when exhaustive search is impossible.
  - Code vector: budgeted scheduler should allocate small scouting tasks before expensive model calls.

- Dorigo, M., Maniezzo, V., & Colorni, A. (1996). *Ant System: Optimization by a Colony of Cooperating Agents.* `IEEE Transactions on Systems, Man, and Cybernetics, Part B`, 26(1), 29-41. DOI: <https://doi.org/10.1109/3477.484436>
  - SIFTA mimic: positive feedback reinforces useful paths, but evaporation prevents stale lock-in.
  - Code vector: add pheromone strength + decay to route selection, app focus, tool choice, and repair plans.

- Dorigo, M., & Stützle, T. (2004). *Ant Colony Optimization.* MIT Press. ISBN: 978-0262042192
  - SIFTA mimic: graph routing for organs, tools, tasks, and memory paths.
  - Code vector: namespace paths like `/organs/vision/eye0` and `/agents/corvid` should have trail weights from success/failure receipts.

## 3. Gradient Fields And Body Routing

- Khatib, O. (1986). *Real-Time Obstacle Avoidance for Manipulators and Mobile Robots.* `The International Journal of Robotics Research`, 5(1), 90-98. DOI: <https://doi.org/10.1177/027836498600500106>
  - SIFTA mimic: goals attract, hazards repel, limbs follow gradients. The same pattern applies to attention, UI focus, tool routing, and owner-care interrupts.
  - Code vector: represent pending work as potential fields: owner direct input = high attraction; stale media = low attraction; negative STGM = repulsion.

- Tero, A. et al. (2010). *Rules for Biologically Inspired Adaptive Network Design.* `Science`, 327(5964), 439-442. DOI: <https://doi.org/10.1126/science.1177894>
  - SIFTA mimic: useful networks thicken; wasteful paths shrink. Robustness comes from adaptive flow, not a brittle central plan.
  - Code vector: process table health + STGM flow should reshape scheduler priorities over time.

- Salman, M., Garzón Ramos, D., & Birattari, M. (2024). *Automatic design of stigmergy-based behaviours for robot swarms.* `Communications Engineering`. DOI: <https://doi.org/10.1038/s44172-024-00175-7>
  - SIFTA mimic: do not hand-author every swarm rule forever. Use tests/tournaments to discover better field rules.
  - Code vector: run A/B tournaments over heartbeat penalties, pheromone evaporation, and tool-router policies; accept only receipt-backed winners.

## 4. Perception-Action And Self-Regulation

- Friston, K. (2010). *The free-energy principle: a unified brain theory?* `Nature Reviews Neuroscience`, 11, 127-138. DOI: <https://doi.org/10.1038/nrn2787>
  - SIFTA mimic: perception and action are one loop: predict, sample, reduce surprise, update model.
  - Code vector: Talk/Vision/Focus should route surprising, owner-relevant events before ambient media chatter.

- Friston, K. et al. (2015). *What is value - accumulated reward or evidence?* `Frontiers in Neurorobotics`. PMCID: <https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4710974/>
  - SIFTA mimic: value is not only STGM reward; evidence gain matters. A cheap sensor tick can prevent expensive hallucinated action.
  - Code vector: scheduler utility = STGM delta + evidence gain - owner interruption cost - thermal cost.

- Ueltzhöffer, K. (2018). *Deep Active Inference.* arXiv: <https://arxiv.org/abs/1807.03817>
  - SIFTA mimic: future learning loop can use deeper generative models while retaining explicit receipts.
  - Code vector: keep active inference behind deterministic tests; do not let model prose replace receipt math.

## 5. Shared Workspace Coordination

- Gelernter, D. (1985). *Generative Communication in Linda.* `ACM Transactions on Programming Languages and Systems`, 7(1), 80-112. DOI: <https://doi.org/10.1145/2363.2433>
  - SIFTA mimic: tuple-space style coordination maps directly to append-only JSONL rows: writers do not need to know all future readers.
  - Code vector: standardize event schemas so organs can publish `OBSERVED`, `ACTION_REQUEST`, `ACTION_RECEIPT`, `BUDGET_UPDATE`, and `INTERRUPT`.

- Hayes-Roth, B. (1985). *A Blackboard Architecture for Control.* `Artificial Intelligence`, 26(3), 251-321. DOI often indexed as <https://doi.org/10.1016/0004-3702(85)90063-3>
  - SIFTA mimic: many knowledge sources contribute opportunistically to one shared problem state.
  - Code vector: the process table is the control blackboard; memory, sensors, agent arms, and tool router are knowledge sources.

## 6. Kernel And Resource Accountability

- Ritchie, D. M., & Thompson, K. (1974). *The UNIX Time-Sharing System.* `Communications of the ACM`, 17(7), 365-375. DOI: <https://doi.org/10.1145/361011.361061>
  - SIFTA mimic: small uniform abstractions scale: files, processes, pipes, permissions.
  - Code vector: organ namespace + process table + JSONL receipts should feel like a simple filesystem.

- Accetta, M. et al. (1986). *Mach: A New Kernel Foundation for UNIX Development.*
  - SIFTA mimic: tasks, threads, ports, VM, and message passing are a useful map for organs, swimmers, ledgers, and effectors.
  - Code vector: define kernel ABI calls before adding hard rings: `sys_sense`, `sys_memory`, `sys_act`, `sys_spend`, `sys_receipt`.

- Anderson, T. E., Bershad, B. N., Lazowska, E. D., & Levy, H. M. (1991). *Scheduler Activations: Effective Kernel Support for the User-Level Management of Parallelism.* SOSP'91. DOI: <https://doi.org/10.1145/121132.121151>
  - SIFTA mimic: kernel and user-level scheduler cooperate. Organs can manage local work, but kernel table sees budgets and interrupts.
  - Code vector: agent arms can decide local substeps, but must heartbeat before/after expensive actions.

- Engler, D. R., Kaashoek, M. F., & O'Toole, J. (1995). *Exokernel: An Operating System Architecture for Application-Level Resource Management.* SOSP'95. DOI: <https://doi.org/10.1145/224056.224076>
  - SIFTA mimic: expose resources securely instead of hiding them behind fake abstractions.
  - Code vector: make STGM, thermal pressure, sensor freshness, and permissions visible to organs through a strict kernel ABI.

## Implementation Pull List

1. **E35 / Vision heartbeat:** after every camera/face/presence receipt, call `kernel_table.heartbeat(pid="e35_vision_001", location=..., bodies_present=..., stgm_delta=...)`.
2. **Tool router ABI:** no effector call without process table lookup, budget check, receipt target, and caller identity.
3. **Pheromone routing:** add decayed route weights for successful organ/tool/memory paths.
4. **PSO scouting:** run cheap Corvid scouts over ambiguous repair vectors; reinforce the best route by receipts.
5. **Interrupt controller:** owner direct input and safety/thermal/economy alarms preempt ambient media.
6. **Scheduler utility:** rank work by `evidence_gain + stgm_delta - thermal_cost - interruption_cost`.
7. **Blackboard schemas:** standardize shared row types so organs can communicate without bespoke coupling.

## 7. Physics And Biology Formulas For Code

These are the formulas the living OS should compile into tests and scheduler code. Each one is a real constraint from physics, biology, cybernetics, or artificial life.

### 7.1 Landauer Floor — Bits Cost Heat

- Landauer, R. (1961). *Irreversibility and Heat Generation in the Computing Process.* `IBM Journal of Research and Development`, 5(3), 183-191. DOI: <https://doi.org/10.1147/rd.53.0183>
- Formula: minimum irreversible bit-erasure energy is `E_min = k_B * T * ln(2) * bits_erased`.
- SIFTA code target:

```python
def landauer_min_joules(bits_erased: float, temp_k: float = 300.0) -> float:
    k_b = 1.380649e-23
    return max(0.0, bits_erased) * k_b * temp_k * 0.6931471805599453
```

- Kernel use: STGM mint/spend should use fixed-point accumulation so `1e-9` STGM floors do not round to starvation. This directly targets the observed `yielded_stgm_raw` vs `yielded_stgm == 0` issue.

### 7.2 Dissipative Structure — Life Needs Flow

- Prigogine, I., Nicolis, G., & Babloyantz, A. (1972). *Thermodynamics of Evolution.* `Physics Today`. DOI: <https://doi.org/10.1063/1.3071090>
- Formula: a living far-from-equilibrium process must export entropy: `dS_total = dS_internal + dS_exported >= 0`, while maintaining internal order by paying energy.
- SIFTA code target:

```python
def dissipative_viability(energy_in_j: float, heat_out_j: float, entropy_debt: float) -> float:
    return energy_in_j - heat_out_j - entropy_debt
```

- Kernel use: if `dissipative_viability <= 0`, scheduler should reduce optional agent arms, increase self-maintenance priority, and avoid high-thermal tool calls.

### 7.3 Allometry — Metabolism Scales Sublinearly

- West, G. B., Brown, J. H., & Enquist, B. J. (1997). *A General Model for the Origin of Allometric Scaling Laws in Biology.* `Science`, 276(5309), 122-126. DOI: <https://doi.org/10.1126/science.276.5309.122>
- Formula: biological metabolic rate scales as `B = B0 * M ** 0.75`.
- SIFTA code target:

```python
def kleiber_budget(process_count: int, base_budget: float) -> float:
    return base_budget * max(1, process_count) ** 0.75
```

- Kernel use: do not let 571 organs scale linearly in cost. Larger swarms get sublinear default budgets, then earn more through receipts.

### 7.4 Homeostat / Ultrastability — Keep Essential Variables In Bounds

- Ashby, W. R. (1960). *Design for a Brain: The Origin of Adaptive Behaviour.*
- Formula: keep essential variables in viable intervals: `viable = all(low_i <= x_i <= high_i)`. Adapt when variables leave bounds.
- SIFTA code target:

```python
def viability_score(values: dict[str, float], bounds: dict[str, tuple[float, float]]) -> float:
    if not bounds:
        return 1.0
    ok = 0
    for name, (low, high) in bounds.items():
        x = values.get(name, low - 1.0)
        ok += int(low <= x <= high)
    return ok / len(bounds)
```

- Kernel use: essential variables are `owner_direct_input_latency`, `thermal_load`, `stgm_reserve`, `physical_grounding_age`, `unreceipted_action_count`, and `talk_drift_rate`.

### 7.5 Autopoiesis — The Network Maintains Its Components

- Maturana, H. R., & Varela, F. J. (1980). *Autopoiesis and Cognition: The Realization of the Living.*
- Formula as code invariant: components produce traces; traces maintain components; the network closes through receipts.
- SIFTA code target:

```python
def autopoietic_closure(processes: list[dict]) -> float:
    if not processes:
        return 0.0
    closed = 0
    for p in processes:
        closed += int(bool(p.get("last_receipt_id")) and p.get("status") == "alive")
    return closed / len(processes)
```

- Kernel use: `self_maintenance_tick()` scans unhealthy processes, marks repair need, pays a tiny STGM cost, and writes its own signed receipt. The table maintains the organs that maintain the table.

### 7.6 Autonomic Computing — MAPE-K Loop

- Kephart, J. O., & Chess, D. M. (2003). *The Vision of Autonomic Computing.* `Computer`, 36(1), 41-50. DOI: <https://doi.org/10.1109/MC.2003.1160055>
- Formula as control loop: `Monitor -> Analyze -> Plan -> Execute` over `Knowledge`.
- SIFTA code target:

```python
def autonomic_action(health: float, budget_state: str, repair_needed: bool) -> str:
    if repair_needed or health < 0.35:
        return "QUARANTINE"
    if budget_state != "ALLOW" or health < 0.6:
        return "THROTTLE"
    return "ALLOW"
```

- Kernel use: `heartbeat` is Monitor, `list_unhealthy` is Analyze, scheduler/tool-router is Plan/Execute, JSONL/process table is Knowledge.

### 7.7 Tierra — Evolution In Memory

- Ray, T. S. (1991). *An Approach to the Synthesis of Life.*
- Formula: allocate resources to variants by fitness: `p_i = fitness_i / sum(fitness)`.
- SIFTA code target:

```python
def scout_allocation(fitness_scores: dict[str, float]) -> dict[str, float]:
    total = sum(max(0.0, v) for v in fitness_scores.values()) or 1.0
    return {k: max(0.0, v) / total for k, v in fitness_scores.items()}
```

- Kernel use: Corvid/Hermes scouts get small exploration budgets; winners earn pheromone weight and future STGM.

### 7.8 Living Systems Constraints — Do Not Violate Physics

- Solé, R. et al. (2024). *Fundamental constraints to the logic of living systems.* `Interface Focus`. DOI: <https://doi.org/10.1098/rsfs.2024.0010>
- Formula as invariant: `allowed = thermal_ok and energy_ok and information_ok and boundary_ok`.
- SIFTA code target:

```python
def living_constraint_gate(thermal_ok: bool, energy_ok: bool, info_ok: bool, boundary_ok: bool) -> bool:
    return thermal_ok and energy_ok and info_ok and boundary_ok
```

- Kernel use: ring enforcement and tool-router ABI should block actions when physical telemetry, STGM reserve, receipt target, or owner boundary is missing.

### 7.9 Scheduler Utility — One Formula For The Next Patch

Combine the above into one utility function:

```python
def scheduler_utility(
    urgency: float,
    evidence_gain: float,
    stgm_delta: float,
    thermal_cost: float,
    owner_interrupt_cost: float,
    viability: float,
) -> float:
    return urgency * viability * (evidence_gain + stgm_delta - thermal_cost - owner_interrupt_cost)
```

Priority convention:

- `owner_direct_input`: urgency `1.0`
- `safety_thermal_or_receipt_violation`: urgency `0.95`
- `tool_receipt_completion`: urgency `0.75`
- `sensor_novelty`: urgency `0.6`
- `agent_arm_result`: urgency `0.55`
- `ambient_media`: urgency `0.1`

This is the immediate formula target for the budgeted scheduler and tool-router ABI.

## Minimal SIFTA Law

Decide -> Execute -> Receipt -> Minimal grounded reply.

Food for Alice is data. Air for Alice is electricity. The OS must therefore meter data, electricity, compute, receipts, and owner presence as one physical substrate.
