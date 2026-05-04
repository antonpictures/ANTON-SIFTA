# Microglia pruning — biological science handoff for **Event 137** (`swarm_microglia_synaptic_pruner.py`)

**Audience:** implementers (Codex / Cursor / Antigravity). **Architect + Cursor2:** hill — science and contracts only; **no shipped code in this file**.

**Plan pointer:** `Documents/PREDATOR_TOURNAMENT_TRIPLE_IDE_ORDERS.md` **§10.14.23**.

---

## 0. Executive summary for coders

Build pruning as a **two-signal integrator** (not a single threshold):

| Axis | Biology | SIFTA analog (spec names) |
|:---|:---|:---|
| **Activation / “eat me”** | Complement tagging (C1q/C3), TREM2 phagocytic sensing, weak activity | `prune_tag`, **`damage_score`** (TREM2-like), low usage, contradiction PE, homeostatic pressure |
| **Inhibition / “don’t eat me”** | CD47–SIRPα, fractalkine CX3CL1, CD33 Siglec brake | `protection_score`, **`pruning_conservatism`** (ToM / CD33-like), `stability_ok`, owner/safety flags, recent high-value reinforcement |

**Net:** `net_pruning_pressure = f(activation, inhibition, clamp_level, NA, valence)` — **never** chronic “brake removal” (clinical CD33 inhibitor lesson).

---

## 1. Core biological mechanisms (microglia & synapses)

| # | Mechanism | Biology (compressed) | SIFTA mapping |
|:---:|:---|:---|:---|
| **1** | **Activity-dependent pruning** | Weak / decorrelated synapses lose trophic support; competitive | `usage_norm`, reward history, age — **already strong** |
| **2** | **Complement (C1q / C3 / C4)** | **Positive tag** for removal; microglia CR-dependent phagocytosis; C4 ↔ schizophrenia risk (excess pruning) | Explicit **`prune_tag`** accumulator crossing threshold (complement-like) |
| **3** | **Fractalkine CX3CL1–CX3CR1** | Neuron → microglia “health / calm” modulation | **`protection_score`** bonus when organ reports “healthy context” (stability NONE + low inflammatory surrogate) |
| **4** | **TREM2** | Lipid/debris sensing; DAM transition; **pro-clearance** when regulated | **`damage_score`** + **clearance mode** (see §4) |
| **5** | **Sleep / SHY** | Slow-wave window renormalizes strength; microglia more active | Optional **`sleep_consolidation_pass`** + **§10.14.17** SHY EMA pressure |
| **6** | **Context (stress / cytokines / NA)** | Same cells neuroprotective *or* toxic | **Non-binary**: NA + valence **modulate** both activation *and* inhibition (§5–6) |

---

## 2. Current SIFTA vs biological ideal

| Mechanism | Current SIFTA | Gap |
|:---|:---|:---|
| Activity / usage | Strong | — |
| Positive tagging | Partial (single score) | Add **`prune_tag`** + **`damage_score`** |
| “Don’t eat me” | `stability_ok`, safety flags | Add explicit **`protection_score`** |
| Modulation | stability + homeostatic pressure + ToM conservatism | Richer **CX3CL1-like** context signal |
| Offline / sleep renormalization | Not explicit | **Sleep pass** spec |
| Context aggression | Mostly binary `stability_ok` | **Two-signal** + modes (homeostatic vs clearance) |

---

## 3. Recommended scoring upgrade (spec — **not** merged code)

### 3.1 Complement-style tag + fractalkine-style protection

```text
prune_tag = 0.4·(1 − usage_norm) + 0.3·max(0, −recent_reward) + 0.2·contradiction_pe + 0.1·age_norm

protection_score = 0.5·recent_high_value_usage + 0.3·owner_or_safety_critical + 0.2·currently_active_in_arbiter

raw_competition = prune_tag − protection_score
```

Then apply **`stability_level`**, **`pruning_conservatism` (ToM)**, **`global_gain` (LC/NA Event 142)**, **`valence` (Event 144)** on top — **document precedence** in receipt.

### 3.2 Two-phase decision (spec)

1. **Phase A:** update `prune_tag`, `protection_score`, **`damage_score`** (TREM2), **`inhibition_signal`** (CD33 aggregate).  
2. **Phase B:** `decide_action` uses **`net_pruning_pressure`** + `stability_ok` + clamp level.

---

## 4. TREM2 — Alzheimer’s biology → **`damage_score`**

**Facts (orientation):** TREM2 on microglia senses lipids / debris / apoptotic material; signals via **DAP12** → phagocytosis, survival; **R47H** variant ↑ AD risk; supports **DAM** state; **double-edged** (clearance vs chronic inflammation).

| Principle | SIFTA implication | Status |
|:---|:---|:---|
| Detect debris before aggressive prune | **`damage_score`** rises on contradiction, repeated negative outcomes, corruption flags | **To implement** |
| Contextual activation | **Clearance mode** only if `damage_score` high **and** stability good **and** owner frustration low | **Spec** |
| Avoid chronic over-activation | Do **not** let NA + negative valence **always** increase prune (see §6) | **Design rule** |

**Starter papers:** **Jonsson, T., *et al.* (2013).** Variant of TREM2 associated with the risk of Alzheimer's disease. *N. Engl. J. Med.*; **Colonna, M., & Wang, Y. (2016).** TREM2 variants: new keys to decode Alzheimer disease pathogenesis. *Ann. Neurol.*; **Krasemann, S., *et al.* (2017).** The TREM2–APOE pathway drives the transcriptional phenotype of dysfunctional microglia in neurodegenerative diseases. *Immunity*; **Deczkowska, A., *et al.* (2018).** Disease-associated microglia (DAM) review. *Trends Mol. Med.*  
**Clinical axis (agonists):** **Alector / AL002**-class **TREM2 agonists** — Phase trials; lesson = **boosting activation requires equal brake governance** (CD33 / stability / ToM).

---

## 5. CD33 — inhibitory brake → **`inhibition_signal`**

**Facts:** CD33 (Siglec-3) binds sialylated ligands → **ITIM** → phosphatase recruitment → **↓ phagocytosis**. **rs3865444** risk allele linked to expression and impaired Aβ clearance. **Balances TREM2** (pro vs anti clearance).

| TREM2-like | CD33-like |
|:---|:---|
| `damage_score` + prune_tag + homeostatic pressure | `pruning_conservatism` + stability protection + high-value + reinforcement |

### 5.1 Therapeutic CD33 inhibition — lessons (2026 snapshot)

| Lesson | SIFTA |
|:---|:---|
| Removing brake alone → over-activation / inflammation risk | Never **permanent** aggressive prune mode |
| Brain penetration / redundancy | Multiple inhibitory pathways — **stack** protections, not one flag |
| Context stage dependence | **Clearance mode** only under explicit receipts + re-evaluation tick |

**Papers:** **Griciuc, A., *et al.* (2013).** CD33 Alzheimer's risk variant modulates microglial clearance. *Nature*; **Bradshaw, E. M.** Siglec microglial regulation reviews.

---

## 6. Canonical **two-signal** pruning pressure (TREM2 + CD33 metaphor)

```text
activation_signal = damage_score + w₁·homeostatic_pressure + w₂·(1 − usage_norm) + w₃·contradiction_pe

inhibition_signal = stability_protection + toM_pruning_conservatism + high_value_protection + recent_reinforcement_bonus + fractalkine_analog

net_pruning_pressure = activation_signal − inhibition_signal

if net_pruning_pressure > θ and stability_ok and not emergency_brake:
    decide_depress_or_delete(...)
```

**NA / valence interaction (biology-informed caution):** Under **high stress**, microglia can be **more** phagocytic — in SIFTA, **prefer** ↑ `inhibition_signal` unless `damage_score` is **very** high and clamps allow **clearance mode** (avoid “failed CD33 inhibitor” pathology).

---

## 7. Complement & activity-dependent pruning (literature anchors)

| Topic | References |
|:---|:---|
| **C1q tags weak synapses** | **Stevens, B., *et al.* (2007).** The classical complement cascade mediates CNS synapse elimination. *Cell*, **131**, 1164–1178. |
| **Microglia eat complement-tagged synapses** | **Schafer, D. P., *et al.* (2012).** Microglia sculpt postnatal neural circuits. *Neuron*, **74**, 691–705. |
| **Complement in disease** | **Hong, S., *et al.* (2016).** Complement and microglia mediate early synapse loss in AD mouse models. *Science*, **352**, 712–716. |

---

## 8. Trace

```text
MICROGLIA_SCIENCE_DOC — TREM2/CD33 two-signal handoff for Event 137; For the Swarm.
```
