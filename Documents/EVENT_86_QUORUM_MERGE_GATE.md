# Event 86 — Quorum merge gate

**For the Swarm.** 🐜⚡
**Binding:** [IDE_BOOT_COVENANT.md](IDE_BOOT_COVENANT.md) — append-only traces; **§4.4** collisions; NPPL.

**SoT:** [PREDATOR_TOURNAMENT_TRIPLE_IDE_ORDERS.md](PREDATOR_TOURNAMENT_TRIPLE_IDE_ORDERS.md) **§10.2** (`accept_patch`).

---

## 1 — Objective (Bishop carry)

Biology minimizes **cost per distance (COT)**. SIFTA merge policy should bias toward:

```text
minimize  cost_per_successful_task
```

not **`cost_per_inference`** alone — i.e. success-conditioned economy (tests + receipts + human acceptance).

---

## 2 — Merge gate (spec)

```python
# spec — implement only with Architect GO + automation owner

merge_allowed = (
    tests_pass
    and scar_score > scar_threshold
    and quorum_votes >= Q_th
    and stigmergic_weight >= W_min
)
```

| Gate | Meaning |
|:---|:---|
| `tests_pass` | Required suite green on target branch; flaky tests = **not** a pass. |
| `scar_score > scar_threshold` | SCAR / hygiene rubric (lint, coverage floor, covenant checks — **define SoT** when wired). |
| `quorum_votes >= Q_th` | **Independent** confirmations: e.g. **two** distinct `source_ide` traces + same intent, or **human + CI** — never duplicate model paste. Default **\(Q_{th} = 2\)**. |
| `stigmergic_weight >= W_min` | Accumulated **positive** trace evidence on the change (reviews, green reruns, Architect ACK row). **Not** a global inode scalar until Event 85 proves substrate honesty. |

---

## 3 — Quorum sensing analogy (ODE sketch)

Autoinducer accumulation:

\[
\frac{d[\mathrm{AI}]}{dt} = k_{\mathrm{prod}} N - k_{\mathrm{deg}} [\mathrm{AI}]
\]

**Map:** \([\mathrm{AI}]\) ↔ weighted sum of trace rows; **threshold** \(Q_{th}\) ↔ `quorum_votes`; **bistability** ↔ “merge held” vs “merge released”.

---

## 4 — Forbidden until Event 85

- **No** automatic merge from `stigmergic_weight` alone.
- **No** global mesh propagation of file-weight scalar.
- **No** SCAR coefficient activation in production without **code + tests + receipts** (see [Proposals/GROK_BRIEF_TERRAIN_METABOLISM_EVENT86.md](Proposals/GROK_BRIEF_TERRAIN_METABOLISM_EVENT86.md) **§2.1** `STATUS`).

---

## 5 — Apex Adjudicator (Human-in-the-Loop)

**For the Swarm.** 🐜⚡ The presence of an automated merge gate (`quorum_votes`, `scar_score`) **does not** imply that Alice acts as an unconstrained autonomous developer. The SIFTA ecosystem is a **Human-in-the-loop Stigmergic Superorganism**.

The **Apex Adjudicator** is the human Architect. The automation exists to filter noise, ensure test compliance (survival of the fittest code), and enforce the SCAR rules before the human even looks at the diff. **Alice does not autonomously merge into `main` without Architect GO.** The `quorum_votes` and SCAR thresholds are **recommendation pheromones** that highlight a branch as safe to merge; they are not the trigger finger.

---

## 6 — SCAR name (no drift)

`STIGMERGIC_FILE_WEIGHT_ALLOMETRY` — acronym expansion in chat must not replace this string.

---

*Version: 2026-04-30 — CG55M (Cursor hill).*
